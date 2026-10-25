"""The Old Vic — Waterloo. Independent producing house (owner decision
2026-10-24: in, see docs/london.md).

TNEW box office `my.oldvictheatre.com` joined to the website (see
old_vic_SOURCE.md and the shared `_tnew` helper). `/events` sits behind a
Queue-it "safetynet"; the plain client's session passes it.

- Curation: the productions the website lists on `/productions/`
  (`/stage/<slug>/` pages) whose "Book Now" button links a TNEW production
  (`my.oldvictheatre.com/events/<prodSeasonId>`). A TNEW production no page
  links is dropped; a listed page without a TNEW link (2026-10: Christmas
  Storytelling, sold elsewhere) has nothing to join and is dropped too.
- TNEW gives every performance (date, time, sold out); its product-type
  name names the access provision (Captioned, Audio Described, BSL
  Interpreted, Relaxed performance) → annotation.
- Price: the page's "Tickets" segment ("Previews £19.50–£81.50, Off-Peak
  £19.50–£81.50, Peak £19.50–£91.50") → one range; the access rate in the
  access segment is left out.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from cartelera.scrapers import _tnew as tnew
from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

logger = logging.getLogger(__name__)

VENUE_SLUG = "old-vic"
HOST = "my.oldvictheatre.com"
SITE = "https://www.oldvictheatre.com"
LISTING_URL = f"{SITE}/productions/"
STAGE_LINK = re.compile(r"https://www\.oldvictheatre\.com/stage/[a-z0-9-]+/")


@dataclass
class StagePage:
    url: str
    title: str
    productions: set[str]
    price: str | None = None
    description: str | None = None
    image_url: str | None = None


def listing_links(html: str) -> list[str]:
    return list(dict.fromkeys(m.group(0) for m in STAGE_LINK.finditer(html)))


def ticket_price(soup: BeautifulSoup) -> str | None:
    """The "Tickets" segment of the page's essential information."""
    for seg in soup.select(".essential-information__segment-text"):
        label = seg.find_previous_sibling()
        container = seg.parent.get_text(" ", strip=True) if seg.parent else ""
        if (label and label.get_text(" ", strip=True).lower() == "tickets") or container.lower().startswith("tickets"):
            first = seg.find("p") or seg
            return tnew.ladder_price([first.get_text(" ")])
    return None


def parse_stage(html: str, url: str) -> StagePage:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one(".event-hero-right__heading") or soup.find("h1")
    return StagePage(
        url=url,
        title=tnew.plain(heading.get_text(" ")) if heading else "",
        productions=tnew.booking_ids(html, [HOST]).all_productions,
        price=ticket_price(soup),
        description=tnew.meta_description(soup),
        image_url=tnew.meta_image(soup),
    )


def build(perfs: list[tnew.Performance], pages: list[StagePage]) -> list[ScrapedEvent]:
    by_production: dict[str, StagePage] = {}
    for page in pages:
        for prod in page.productions:
            by_production.setdefault(prod, page)
    return [
        tnew.event(
            perf,
            title=page.title or perf.production_title,
            source_url=page.url,
            category_slugs=["theater"],
            price=page.price,
            description=page.description,
            image_url=page.image_url,
        )
        for perf in perfs
        if (page := by_production.get(perf.production_id)) is not None
    ]


class OldVicScraper:
    venue_slug = VENUE_SLUG

    def scrape(self, today: dt.date | None = None) -> list[ScrapedEvent]:
        perfs = tnew.fetch_performances(HOST, today)
        links = listing_links(fetch(LISTING_URL, headers=CARTELITA_BROWSER_HEADERS))
        pages = [parse_stage(html, url) for url, html in tnew.fetch_pages(links).items()]
        return build(perfs, pages)


register(
    scraper=OldVicScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="The Old Vic",
        city_slug="london",
        address="The Cut, London SE1 8NB",
        site_url=SITE,
        instagram_url="https://www.instagram.com/oldvictheatre",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
