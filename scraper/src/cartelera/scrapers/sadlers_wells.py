"""Sadler's Wells — London's dance house, four stages in three buildings.

The website's what's-on, cross-checked with the TNEW box office
`my.sadlerswells.com` (see sadlers_wells_SOURCE.md and the shared `_tnew`
helper). One source, three venues, because the stages sit in three
buildings: Sadler's Wells Theatre and its Lilian Baylis Studio (Rosebery
Avenue, Islington) → `sadlers-wells`; the Peacock Theatre (Holborn) →
`peacock-theatre`; Sadler's Wells East (Stratford) → `sadlers-wells-east`.

- Curation: the show pages the what's-on listing (`/whats-on/`, paginated)
  links — the venue's own public programme. The box office also sells
  classes (DF …, Artist-Led Sessions), touch tours, audio-description
  headsets and hires that the site doesn't list; they never show up here.
- Every show page renders each performance as a `c-event-instance` block:
  date without year ("Tuesday 3 November"), time, stage
  (`c-event-instance__venue-name`), price ("From: £15.00"), and — while it
  can be booked online — the TNEW booking link (`…/<prodSeasonId>/<perfId>`).
  Sold-out and not-yet-on-sale performances keep their block but lose the
  link, which is why the website (not the TNEW feed) is the primary source.
- TNEW gives the exact date of every linked performance (the year) and its
  sold-out status; unlinked blocks get the year from their weekday. A TNEW
  outage only loses that cross-check, never the run.
- external_id: the site's own per-performance id (`#instance-<id>`).
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from cartelera.scrapers import _tnew as tnew
from cartelera.scrapers import register_source
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.scrapers.price import gbp_amounts
from cartelera.types import ListMembership, ScrapedEvent, SourceDefinition, VenueDefinition

logger = logging.getLogger(__name__)

SOURCE_SLUG = "sadlers-wells"
HOST = "my.sadlerswells.com"
SITE = "https://www.sadlerswells.com"
LISTING_URL = f"{SITE}/whats-on/"
SHOW_LINK = re.compile(r"https://www\.sadlerswells\.com/whats-on/[a-z0-9-]+/")
MAX_LISTING_PAGES = 20

# The stage named on each performance → our venue (a building).
VENUE_OF_STAGE = {
    "Sadler's Wells Theatre": "sadlers-wells",
    "Lilian Baylis Studio": "sadlers-wells",
    "Peacock Theatre": "peacock-theatre",
    "Sadler's Wells East": "sadlers-wells-east",
}
# Stages worth naming on the event (the venue name already says the rest).
ROOM_ANNOTATION = {"Lilian Baylis Studio": "Lilian Baylis Studio"}

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}
_WEEKDAYS = {d: i for i, d in enumerate(
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])}
_DATE = re.compile(r"([A-Za-z]+)\s+(\d{1,2})\s+([A-Za-z]+)")
_TIME = re.compile(r"(\d{1,2})(?:[:.](\d{2}))?\s*([ap]m)", re.IGNORECASE)


@dataclass
class Instance:
    """One performance block of a show page."""

    instance_id: str
    weekday: int
    day: int
    month: int
    time: dt.time | None
    stage: str
    price: str | None
    sold_out: bool
    booking: tuple[str, str] | None  # (prodSeasonId, perfId) while bookable online
    access: list[str] = field(default_factory=list)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'")).strip()


def parse_listing(html: str) -> tuple[dict[str, str], list[str]]:
    """(show-page URL → title, further listing-page URLs) of one what's-on
    page. Titles come from the cards' accessible names ("Company - Show")."""
    soup = BeautifulSoup(html, "html.parser")
    shows: dict[str, str] = {}
    for card in soup.select(".c-event-card"):
        link = card.select_one("a.c-event-card__cover-link[href]")
        if not link or not SHOW_LINK.fullmatch(link["href"]):
            continue
        name = link.select_one(".u-hidden-visually")
        shows.setdefault(link["href"], _norm(name.get_text(" ") if name else card.get_text(" ")))
    pages = [urljoin(LISTING_URL, a["href"]) for a in soup.select(".c-pagination a.page-numbers[href]")]
    return shows, list(dict.fromkeys(pages))


def price_label(text: str) -> str | None:
    """"From: £15.00" → "from £15" (the site states only the cheapest
    ticket); "From: £0.00" → "free"; no amount → None."""
    amounts = gbp_amounts(text)
    if not amounts:
        return None
    low = min(amounts)
    return "free" if low <= 0 else f"from {tnew.price_range([low])}"


def parse_time(text: str) -> dt.time | None:
    """"7:30 pm" / "2 pm" / "10 am" → time."""
    m = _TIME.search(text)
    if not m:
        return None
    hour = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "pm" else 0)
    return dt.time(hour, int(m.group(2) or 0))


def parse_show(html: str) -> list[Instance]:
    """A show page's performance blocks."""
    soup = BeautifulSoup(html, "html.parser")
    access: dict[str, list[str]] = {}
    for block in soup.select(".c-access-type"):
        label = _norm(block.select_one(".c-access-type__title").get_text(" ")).lower()
        label = re.sub(r"performances\b", "performance", label)
        for a in block.select(".c-access-type__instances a[href^='#instance-']"):
            access.setdefault(a["href"].removeprefix("#instance-"), []).append(label)
    out: list[Instance] = []
    for block in soup.select(".c-event-instance"):
        anchor = block.select_one(".c-event-instance__anchor[id^='instance-']")
        date_el = block.select_one(".c-event-instance__date")
        m = _DATE.search(date_el.get_text(" ")) if date_el else None
        if not anchor or not m or m.group(1).lower() not in _WEEKDAYS or m.group(3).lower() not in _MONTHS:
            logger.warning("sadlers-wells: unparseable performance block %r", block.get_text(" ", strip=True)[:80])
            continue
        time_el = block.select_one(".c-event-instance__time")
        stage_el = block.select_one(".c-event-instance__venue-name")
        price_el = block.select_one(".c-event-instance__price")
        actions = block.select_one(".c-event-instance__actions")
        ids = tnew.booking_ids(str(block), [HOST]).performances
        instance_id = anchor["id"].removeprefix("instance-")
        out.append(Instance(
            instance_id=instance_id,
            weekday=_WEEKDAYS[m.group(1).lower()],
            day=int(m.group(2)),
            month=_MONTHS[m.group(3).lower()],
            time=parse_time(time_el.get_text(" ")) if time_el else None,
            stage=_norm(stage_el.get_text(" ")) if stage_el else "",
            price=price_label(price_el.get_text(" ")) if price_el else None,
            sold_out="sold out" in (actions.get_text(" ") if actions else "").lower(),
            booking=next(iter(ids)) if len(ids) == 1 else None,
            access=access.get(instance_id, []),
        ))
    return out


def resolve_date(inst: Instance, today: dt.date) -> dt.date | None:
    """The block's date: the first year from last year on whose calendar the
    day falls on the stated weekday and isn't long past (the site lists
    upcoming performances, a year has its weekdays shifted by 1–2 days, so
    the match is unambiguous within the window)."""
    for year in range(today.year - 1, today.year + 3):
        try:
            date = dt.date(year, inst.month, inst.day)
        except ValueError:
            continue
        if date.weekday() == inst.weekday and date >= today - dt.timedelta(days=7):
            return date
    return None


def build(
    shows: dict[str, str],
    pages: dict[str, list[Instance]],
    perfs: list[tnew.Performance],
    today: dt.date,
) -> list[ScrapedEvent]:
    """One event per performance block of a listed show page, from today to
    today + WINDOW_DAYS."""
    by_key = {(p.production_id, p.performance_id): p for p in perfs}
    horizon = today + dt.timedelta(days=tnew.WINDOW_DAYS)
    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for url, instances in pages.items():
        # The production's listing image, from any performance TNEW knows.
        image = next((by_key[i.booking].image_url for i in instances if i.booking in by_key), None)
        for inst in instances:
            if inst.instance_id in seen:
                continue
            seen.add(inst.instance_id)
            venue = VENUE_OF_STAGE.get(inst.stage)
            if venue is None:
                logger.warning("sadlers-wells: unknown stage %r on %s", inst.stage, url)
                continue
            perf = by_key.get(inst.booking) if inst.booking else None
            if perf is not None:
                start_date, start_time = perf.start.date(), perf.start.time()
                if perf.start.time() != inst.time:
                    logger.warning("sadlers-wells: %s instance %s: site %s, TNEW %s",
                                   url, inst.instance_id, inst.time, perf.start)
            else:
                start_date, start_time = resolve_date(inst, today), inst.time
            if start_date is None or not (today <= start_date < horizon):
                continue
            sold_out = inst.sold_out or (perf is not None and perf.sold_out)
            room = ROOM_ANNOTATION.get(inst.stage)
            events.append(ScrapedEvent(
                title=shows[url],
                start_date=start_date,
                start_time=start_time,
                source_url=url,
                category_slugs=["dance"],
                price="sold-out" if sold_out else inst.price,
                image_url=image,
                external_id=inst.instance_id,
                annotations=[*([room] if room else []), *inst.access],
                venue_slug=venue,
            ))
    return sorted(events, key=lambda e: (e.start_date, e.start_time or dt.time(0), e.title))


def fetch_listing() -> dict[str, str]:
    """Every show page the what's-on listing links (all its pages)."""
    shows: dict[str, str] = {}
    queue, done = [LISTING_URL], set()
    while queue and len(done) < MAX_LISTING_PAGES:
        url = queue.pop(0)
        if url in done:
            continue
        done.add(url)
        found, pages = parse_listing(fetch(url, headers=CARTELITA_BROWSER_HEADERS))
        for show, title in found.items():
            shows.setdefault(show, title)
        queue += [p for p in pages if p not in done]
    return shows


class SadlersWellsScraper:
    def scrape(self, today: dt.date | None = None) -> list[ScrapedEvent]:
        today = today or dt.date.today()
        shows = fetch_listing()
        pages = {url: parse_show(html) for url, html in tnew.fetch_pages(shows).items()}
        try:
            perfs = tnew.fetch_performances(HOST, today)
        except Exception as exc:  # the cross-check only; the site suffices
            logger.warning("sadlers-wells: TNEW feed unavailable (%s); dates from the site alone", exc)
            perfs = []
        return build(shows, pages, perfs, today)


def _venue(slug: str, name: str, address: str, site_url: str) -> VenueDefinition:
    return VenueDefinition(
        slug=slug,
        name=name,
        city_slug="london",
        address=address,
        site_url=site_url,
        instagram_url="https://www.instagram.com/sadlers_wells",
        category_slugs=["dance"],
        list_memberships=[ListMembership(list_slug="dance")],
    )


register_source(
    SadlersWellsScraper(),
    SourceDefinition(
        slug=SOURCE_SLUG,
        name="Sadler's Wells",
        venues=[
            _venue("sadlers-wells", "Sadler's Wells", "Rosebery Avenue, London EC1R 4TN",
                   f"{SITE}/your-visit/sadlers-wells-theatre/"),
            _venue("peacock-theatre", "Peacock Theatre", "Portugal Street, London WC2A 2HT",
                   f"{SITE}/your-visit/peacock-theatre/"),
            _venue("sadlers-wells-east", "Sadler's Wells East", "Stratford Walk, Queen Elizabeth Olympic Park, London E20 2AR",
                   f"{SITE}/your-visit/sadlers-wells-east/"),
        ],
    ),
)
