"""Southbank Centre (Royal Festival Hall, Queen Elizabeth Hall, Purcell Room,
Clore Ballroom) — South Bank. One owning source for all its categories.

The website alone (see southbank_centre_SOURCE.md). Its box office is TNEW
(`secure.southbankcentre.co.uk`, open like the other TNEW hosts, see
`_tnew`), but that feed is no use here: it sells seating products as
separate "performances" at the same time (Cirque Alice: 68 TNEW rows for 34
shows, half of them "Onstage ringside tables") and has no category. The
website has everything per performance:

- Listing: `/whats-on/?artform-filter=<artform>` (12 cards a page,
  `/whats-on/page/N/?artform-filter=…`), crawled for the artforms we map.
  Each card shows the event's PRIMARY artform pill
  (`c-event-card__primary-artform`); a filter also lists events whose
  secondary artform matches, so the pill — not the filter — decides.
- Event page (`/whats-on/<slug>/`): one JSON-LD event per performance
  (`MusicEvent` / `TheaterEvent` / `ChildrensEvent`) with `startDate`,
  `location.name` (the hall), `offers` (`AggregateOffer` low/high price,
  `availability`), plus the masthead's primary-artform pill and its series
  (`c-event-masthead__group-item` → `/events/<series>/`).

Category = the site's primary artform: Classical music → classical;
Performance & dance → theater + dance (one label for both; the site gives
no finer split — every such page is a JSON-LD TheaterEvent); Family → kids;
Gigs → pop, or jazz when the event belongs to the EFG London Jazz Festival
series (the site's own series; it has no genre below "Gigs"). Every other
artform (Literature & poetry, Comedy, Talks & debates, Art & exhibitions,
Courses & workshops, Tours & activities, Online events, Young people) is
out of scope.

The website is behind Cloudflare: fetched with curl_cffi (`impersonate`).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from cartelera.scrapers import _tnew as tnew
from cartelera.scrapers import register
from cartelera.scrapers.http import fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

logger = logging.getLogger(__name__)

VENUE_SLUG = "southbank-centre"
SITE = "https://www.southbankcentre.co.uk"
ARTFORM_FILTERS = ("classical-music", "gigs", "performance-dance", "family")
EVENT_LINK = re.compile(r"https://www\.southbankcentre\.co\.uk/whats-on/[a-z0-9-]+/")
MAX_LISTING_PAGES = 30
JAZZ_SERIES = "/events/efg-london-jazz-festival/"
# The site's primary artform → our categories (None: the series decides).
PILL_CATEGORIES: dict[str, list[str] | None] = {
    "Classical music": ["classical"],
    "Performance & dance": ["theater", "dance"],
    "Family": ["kids"],
    "Gigs": None,
}


@dataclass
class Performance:
    start: dt.datetime  # venue-local, naive
    hall: str
    price: str | None
    sold_out: bool


@dataclass
class EventPage:
    url: str
    title: str
    artform: str
    series: list[tuple[str, str]]  # (name, URL)
    performances: list[Performance] = field(default_factory=list)
    description: str | None = None
    image_url: str | None = None

    @property
    def slug(self) -> str:
        return self.url.rstrip("/").rsplit("/", 1)[-1]


def listing_url(artform: str) -> str:
    return f"{SITE}/whats-on/?artform-filter={artform}"


def parse_listing(html: str, page_url: str) -> tuple[dict[str, str], list[str]]:
    """(event URL → primary-artform pill, further listing-page URLs of the
    same filter) of one listing page."""
    soup = BeautifulSoup(html, "html.parser")
    cards: dict[str, str] = {}
    for card in soup.select(".c-event-card"):
        link = card.select_one("a.c-event-card__cover-link[href]")
        pill = card.select_one(".c-event-card__primary-artform")
        if link and pill and EVENT_LINK.fullmatch(link["href"]):
            cards.setdefault(link["href"], tnew.plain(pill.get_text(" ")))
    artform = re.search(r"artform-filter=([a-z0-9-]+)", page_url)
    pages = []
    for a in soup.select('a[href*="/whats-on/page/"]'):
        href = urljoin(page_url, a["href"])
        if artform and f"artform-filter={artform.group(1)}" in href:
            pages.append(href)
    return cards, list(dict.fromkeys(pages))


def _offer_price(offers: dict | list | None) -> tuple[str | None, bool]:
    offer = offers[0] if isinstance(offers, list) and offers else offers
    if not isinstance(offer, dict):
        return None, False
    sold_out = "soldout" in str(offer.get("availability") or "").lower()
    amounts: list[float] = []
    for key in ("lowPrice", "highPrice", "price"):
        try:
            amounts.append(float(offer[key]))
        except (KeyError, TypeError, ValueError):
            pass
    price = tnew.price_range(amounts)
    # Free drop-in events ("Free – no ticket required") are flagged SoldOut
    # because nothing can be booked; they're free, not sold out.
    return price, sold_out and price != "free"


def parse_event(html: str, url: str) -> EventPage:
    soup = BeautifulSoup(html, "html.parser")
    pill = soup.select_one(".c-event-masthead__primary-artform")
    artform = ""
    if pill:
        hidden = pill.select_one(".u-hidden-visually")
        if hidden:
            hidden.extract()
        artform = tnew.plain(pill.get_text(" "))
    series = [
        (tnew.plain(a.get_text(" ")), urljoin(SITE, a["href"]))
        for a in soup.select(".c-event-masthead__group-item a[href]")
    ]
    title_el = soup.select_one(".c-event-masthead__title")
    intro = soup.select_one(".c-event-masthead__intro")
    page = EventPage(
        url=url,
        title=tnew.plain(title_el.get_text(" ")) if title_el else "",
        artform=artform,
        series=series,
        description=tnew.plain(intro.get_text(" ")) if intro else None,
    )
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if not isinstance(item, dict) or "Event" not in str(item.get("@type")):
                continue
            try:
                start = dt.datetime.fromisoformat(item["startDate"])
            except (KeyError, TypeError, ValueError):
                continue
            if start.tzinfo is not None:
                start = start.astimezone(tnew.LONDON).replace(tzinfo=None)
            price, sold_out = _offer_price(item.get("offers"))
            page.performances.append(Performance(
                start=start,
                hall=tnew.plain((item.get("location") or {}).get("name")),
                price=price,
                sold_out=sold_out,
            ))
            if not page.title:
                page.title = tnew.plain(item.get("name"))
            if page.image_url is None:
                image = item.get("image")
                page.image_url = (image[0] if isinstance(image, list) and image else image) or None
    return page


def categories(page: EventPage) -> list[str]:
    """The page's primary artform → our categories ([] = out of scope)."""
    if page.artform not in PILL_CATEGORIES:
        return []
    cats = PILL_CATEGORIES[page.artform]
    if cats is not None:
        return list(cats)
    return ["jazz"] if any(JAZZ_SERIES in u for _n, u in page.series) else ["pop"]


def build(pages: list[EventPage], today: dt.date) -> list[ScrapedEvent]:
    horizon = today + dt.timedelta(days=tnew.WINDOW_DAYS)
    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for page in pages:
        cats = categories(page)
        if not cats:
            continue
        for perf in sorted(page.performances, key=lambda p: p.start):
            if not (today <= perf.start.date() < horizon):
                continue
            ext = f"{page.slug}@{perf.start:%Y-%m-%dT%H:%M}"
            if ext in seen:
                continue
            seen.add(ext)
            events.append(ScrapedEvent(
                title=page.title,
                start_date=perf.start.date(),
                start_time=perf.start.time(),
                source_url=page.url,
                category_slugs=cats,
                price="sold-out" if perf.sold_out else perf.price,
                description=page.description,
                image_url=page.image_url,
                external_id=ext,
                annotations=[a for a in dict.fromkeys([perf.hall, *(n for n, _u in page.series)]) if a],
            ))
    return sorted(events, key=lambda e: (e.start_date, e.start_time or dt.time(0), e.title))


def fetch_listings() -> dict[str, str]:
    """Event URL → primary artform, over every page of each mapped filter."""
    cards: dict[str, str] = {}
    for artform in ARTFORM_FILTERS:
        queue, done = [listing_url(artform)], set()
        while queue and len(done) < MAX_LISTING_PAGES:
            url = queue.pop(0)
            if url in done:
                continue
            done.add(url)
            found, pages = parse_listing(fetch(url, impersonate=True), url)
            for event_url, pill in found.items():
                cards.setdefault(event_url, pill)
            queue += [p for p in pages if p not in done]
    return cards


class SouthbankCentreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self, today: dt.date | None = None) -> list[ScrapedEvent]:
        today = today or dt.date.today()
        cards = fetch_listings()
        wanted = [url for url, pill in cards.items() if pill in PILL_CATEGORIES]
        html = tnew.fetch_pages(wanted, impersonate=True)
        return build([parse_event(page, url) for url, page in html.items()], today)


register(
    scraper=SouthbankCentreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Southbank Centre",
        city_slug="london",
        address="Belvedere Road, London SE1 8XX",
        site_url=SITE,
        instagram_url="https://www.instagram.com/southbankcentre",
        category_slugs=["classical", "theater", "dance", "kids", "pop", "jazz"],
        list_memberships=[
            ListMembership(list_slug=c, whitelist_category_slug=c)
            for c in ("classical", "theater", "dance", "kids", "pop", "jazz")
        ],
    ),
)
