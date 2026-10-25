"""Shakespeare's Globe (Globe Theatre + Sam Wanamaker Playhouse) — Bankside.

TNEW box office `basket.shakespearesglobe.com` joined to the website's
what's-on (see shakespeares_globe_SOURCE.md and the shared `_tnew` helper).
`/events` sits behind a Queue-it "safetynet"; the plain client's session
passes it.

- Curation: the website's what's-on groups its cards in sections; only the
  PERFORMANCES section (`section#performances`, sub-headed Globe Theatre /
  Sam Wanamaker Playhouse) is kept. The other sections — Guided Tours,
  Climate Action (MakeBeth, an outdoor Bankside show, is filed here, not
  under Performances), Family Events & Tours, Shakespeare & Race Festival,
  Young People (workshops, courses), Teacher Training (CPD) — and the TNEW
  products the site doesn't list at all (the Exhibition, library visits,
  talks, Telling Tales, touch tours) are dropped.
- A show page links each performance to TNEW (`…/<prodSeasonId>/<perfId>`)
  in its "Dates & Tickets" list, with a per-performance price line
  (`.c-event-listing__price`: "Prices: £89.00 - £29.00* | Standing: £5.00,
  £10.00"; the masthead's "Prices: £89.00 - £5.00" when a line is empty).
- TNEW gives every performance of those productions (date, time, sold out).
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from cartelera.scrapers import _tnew as tnew
from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

logger = logging.getLogger(__name__)

VENUE_SLUG = "shakespeares-globe"
HOST = "basket.shakespearesglobe.com"
SITE = "https://www.shakespearesglobe.com"
LISTING_URL = f"{SITE}/whats-on/"
SHOW_LINK = re.compile(r"https://www\.shakespearesglobe\.com/whats-on/[a-z0-9-]+/")
PROGRAMME_SECTION = "section#performances"


@dataclass
class ShowPage:
    url: str
    title: str
    productions: set[str]
    prices: dict[str, str | None] = field(default_factory=dict)  # perfId → price
    price: str | None = None  # the masthead's
    room: str = ""
    description: str | None = None
    image_url: str | None = None


def listing_links(html: str) -> list[str]:
    """The show pages of the what's-on PERFORMANCES section."""
    soup = BeautifulSoup(html, "html.parser")
    section = soup.select_one(PROGRAMME_SECTION)
    if section is None:
        raise ValueError("Globe what's-on: no PERFORMANCES section")
    links = [a["href"] for a in section.select("a.c-event-card__cover-link[href]")]
    return [u for u in dict.fromkeys(links) if SHOW_LINK.fullmatch(u)]


def parse_show(html: str, url: str) -> ShowPage:
    soup = BeautifulSoup(html, "html.parser")
    prices: dict[str, str | None] = {}
    for slot in soup.select(".c-event-listing .c-time-slot"):
        price_el = slot.select_one(".c-event-listing__price")
        price = tnew.ladder_price([price_el.get_text(" ")]) if price_el else None
        for _prod, perf in tnew.booking_ids(str(slot), [HOST]).performances:
            prices[perf] = price
    title = soup.select_one(".c-event-listings h2") or soup.find("h1")
    masthead = soup.select_one(".c-masthead__price-label")
    room = soup.select_one(".c-event-locations [role=listitem]")
    return ShowPage(
        url=url,
        title=tnew.plain(title.get_text(" ")) if title else "",
        productions=tnew.booking_ids(html, [HOST]).all_productions,
        prices=prices,
        price=tnew.ladder_price([masthead.get_text(" ")]) if masthead else None,
        room=tnew.plain(room.get_text(" ")) if room else "",
        description=tnew.meta_description(soup),
        image_url=tnew.meta_image(soup),
    )


def build(perfs: list[tnew.Performance], pages: list[ShowPage]) -> list[ScrapedEvent]:
    by_production: dict[str, ShowPage] = {}
    for page in pages:
        for prod in page.productions:
            by_production.setdefault(prod, page)
    events: list[ScrapedEvent] = []
    for perf in perfs:
        page = by_production.get(perf.production_id)
        if page is None:
            continue
        events.append(tnew.event(
            perf,
            title=page.title or perf.production_title,
            source_url=page.url,
            category_slugs=["theater"],
            price=page.prices.get(perf.performance_id) or page.price,
            description=page.description,
            image_url=page.image_url,
            annotations=[page.room] if page.room else [],
        ))
    return events


class ShakespearesGlobeScraper:
    venue_slug = VENUE_SLUG

    def scrape(self, today: dt.date | None = None) -> list[ScrapedEvent]:
        perfs = tnew.fetch_performances(HOST, today)
        links = listing_links(fetch(LISTING_URL, headers=CARTELITA_BROWSER_HEADERS))
        pages = [parse_show(html, url) for url, html in tnew.fetch_pages(links).items()]
        return build(perfs, pages)


register(
    scraper=ShakespearesGlobeScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Shakespeare's Globe",
        city_slug="london",
        address="21 New Globe Walk, London SE1 9DT",
        site_url=SITE,
        instagram_url="https://www.instagram.com/the_globe",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
