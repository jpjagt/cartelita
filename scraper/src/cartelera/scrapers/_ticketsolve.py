"""Ticketsolve public XML feeds — shared by the venues on a Ticketsolve box
office (UK/Irish theatres, arts centres, halls).

Every Ticketsolve client publishes its programme, unauthenticated, at
`https://<client>.ticketsolve.com/shows.xml` (some on a custom domain, e.g.
New Diorama's `newdiorama-tickets.newdiorama.com/shows.xml`):

    venues/venue (name) → shows/show (id, name, description, event_category,
    url, tags/tag, images) → events/event (id, date_time_iso, event_attribute,
    venue_layout, url, status, feed/url)

— one `event` per performance, so one row per occurrence comes for free.
Each event's own feed (`…/events/<id>.xml`) adds its `prices` (`type`,
`face_price`), `available` and `capacity`; it's one small request per
performance (~2 KB), made only for performances that aren't sold out.

The curation is the venue module's: a `keep(venue, show, event)` callback
returning our categories ([] drops the performance), on the feed's own
fields (`event_category`, tags, venue name). Online streams
(`event_attribute` "Online" / layout "ONLINE") never count as a
performance at the venue and are always dropped. See ticketsolve_SOURCE.md.

Private module (leading underscore): skipped by `load_all()`.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

import httpx

from cartelera.scrapers.http import CARTELITA_COMPAT_UA
from cartelera.scrapers.price import format_gbp, format_gbp_range
from cartelera.types import ScrapedEvent

logger = logging.getLogger(__name__)

LONDON = ZoneInfo("Europe/London")
MAX_CONCURRENCY = 3
TIMEOUT = 30
# Price types that name the standard full-price ticket; when an event has
# one, concession/discount/supporter tiers don't count.
STANDARD_TYPES = re.compile(r"(?i)^\s*(standard|full price|full|general admission|adult|adults)\s*$")
# event_attribute values that only say where/how, not what kind of performance.
_PLAIN_ATTRIBUTES = {"", "in person"}


@dataclass
class Performance:
    id: str
    start: dt.datetime  # Europe/London wall clock
    url: str
    status: str
    attribute: str
    layout: str
    feed_url: str | None


@dataclass
class Show:
    id: str
    name: str
    venue: str
    category: str
    tags: list[str]
    url: str
    description: str | None
    image_url: str | None
    events: list[Performance] = field(default_factory=list)


# (show, performance) -> our categories; [] drops the performance.
Keep = Callable[[Show, Performance], list[str]]


def _text(el: ET.Element | None, path: str) -> str:
    return ((el.findtext(path) if el is not None else None) or "").strip()


def _html_text(fragment: str) -> str | None:
    from bs4 import BeautifulSoup

    text = BeautifulSoup(fragment, "html.parser").get_text(" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def parse_shows(xml: str | bytes) -> list[Show]:
    """`shows.xml` → every show with its performances."""
    root = ET.fromstring(xml.encode() if isinstance(xml, str) else xml)
    shows: list[Show] = []
    for venue in root.iter("venue"):
        venue_name = _text(venue, "name")
        for show in venue.iter("show"):
            image = show.find("images/image/url[@size='large']")
            s = Show(
                id=show.get("id") or "",
                name=re.sub(r"\s+", " ", _text(show, "name")),
                venue=venue_name,
                category=_text(show, "event_category"),
                tags=[(t.text or "").strip() for t in show.iter("tag")],
                url=_text(show, "url"),
                description=_html_text(_text(show, "description")),
                image_url=(image.text or "").strip() if image is not None else None,
            )
            for ev in show.iter("event"):
                start = dt.datetime.fromisoformat(_text(ev, "date_time_iso"))
                s.events.append(Performance(
                    id=ev.get("id") or _text(ev, "event_number"),
                    start=start.astimezone(LONDON).replace(tzinfo=None),
                    url=_text(ev, "url"),
                    status=_text(ev, "status").lower(),
                    attribute=_text(ev, "event_attribute"),
                    layout=_text(ev, "venue_layout"),
                    feed_url=_text(ev, "feed/url") or None,
                ))
            shows.append(s)
    return shows


def is_online(perf: Performance) -> bool:
    return perf.attribute.lower() == "online" or perf.layout.upper() == "ONLINE"


def price_text(event_xml: str | bytes) -> str | None:
    """A performance's own feed → house convention: the standard ticket
    (`STANDARD_TYPES`) when the event has one, else the spread of every paid
    tier ("£5–25" for a pay-what-you-can ladder; 2x rule); all zero →
    "free"; no prices → None."""
    root = ET.fromstring(event_xml.encode() if isinstance(event_xml, str) else event_xml)
    prices: list[tuple[str, float]] = []
    for p in root.iter("price"):
        amount = _text(p, "face_price") or _text(p, "selling_price")
        try:
            prices.append((_text(p, "type"), float(amount)))
        except ValueError:
            continue
    if not prices:
        return None
    standard = [a for t, a in prices if STANDARD_TYPES.match(t) and a > 0]
    if standard:
        return format_gbp(max(standard))
    paid = [a for _t, a in prices if a > 0]
    if not paid:
        return "free"
    return format_gbp_range(min(paid), max(paid))


def annotations(perf: Performance) -> list[str]:
    """The performance's `event_attribute` ("PREVIEW", "Relaxed Show",
    "Captioned Performance") as a lowercase label."""
    label = re.sub(r"\s+", " ", perf.attribute).strip().lower()
    return [] if label in _PLAIN_ATTRIBUTES or label == "online" else [label]


def select(shows: list[Show], keep: Keep, today: dt.date) -> list[tuple[Show, Performance, list[str]]]:
    """(show, performance, categories) for every upcoming, not cancelled,
    in-venue performance the venue keeps, in start order."""
    out = []
    for show in shows:
        for perf in show.events:
            if perf.start.date() < today or is_online(perf) or perf.status in ("cancelled", "canceled"):
                continue
            cats = keep(show, perf)
            if cats:
                out.append((show, perf, cats))
    return sorted(out, key=lambda item: item[1].start)


def fetch_prices(perfs: list[Performance], client: httpx.Client) -> dict[str, str | None]:
    """Performance id → price text from its own feed (sold-out performances
    aren't asked). A failed lookup is an unknown price, never a failed run."""

    def one(perf: Performance) -> tuple[str, str | None]:
        if not perf.feed_url:
            return perf.id, None
        try:
            resp = client.get(perf.feed_url)
            resp.raise_for_status()
            return perf.id, price_text(resp.content)
        except (httpx.HTTPError, ET.ParseError) as exc:
            logger.warning("ticketsolve: no price for %s (%s)", perf.feed_url, exc)
            return perf.id, None

    todo = [p for p in perfs if p.status != "sold out"]
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        return dict(pool.map(one, todo))


def build(
    selected: list[tuple[Show, Performance, list[str]]],
    prices: dict[str, str | None],
    *,
    title: Callable[[Show], str] | None = None,
    venue: Callable[[Show, Performance], str | None] | None = None,
) -> list[ScrapedEvent]:
    events = []
    for show, perf, cats in selected:
        events.append(ScrapedEvent(
            title=title(show) if title else show.name,
            start_date=perf.start.date(),
            start_time=perf.start.time(),
            source_url=perf.url or show.url,
            category_slugs=list(cats),
            price="sold-out" if perf.status == "sold out" else prices.get(perf.id),
            description=show.description,
            image_url=show.image_url,
            external_id=perf.id,
            annotations=annotations(perf),
            venue_slug=venue(show, perf) if venue else None,
        ))
    return events


def http_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": CARTELITA_COMPAT_UA, "Accept": "application/xml"},
        follow_redirects=True,
        timeout=TIMEOUT,
    )


def scrape(
    feed_url: str,
    keep: Keep,
    *,
    today: dt.date | None = None,
    title: Callable[[Show], str] | None = None,
    venue: Callable[[Show, Performance], str | None] | None = None,
) -> list[ScrapedEvent]:
    """The whole pipeline for one feed: shows.xml → curation (`keep`) →
    prices (per kept performance) → ScrapedEvents."""
    today = today or dt.date.today()
    with http_client() as client:
        resp = client.get(feed_url)
        resp.raise_for_status()
        selected = select(parse_shows(resp.content), keep, today)
        prices = fetch_prices([perf for _s, perf, _c in selected], client)
    return build(selected, prices, title=title, venue=venue)
