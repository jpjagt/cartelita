"""Donmar Warehouse (Covent Garden).

Spektrix client `donmarwarehouse`, via the shared `_spektrix` helper (see
donmar_warehouse_SOURCE.md). The box office's `Website` attribute:
"Performance" is programme; "Development event" (script conversations, the
"Supercool Test Event") is not.

Event pages on donmarwarehouse.com come from the site's search index
(`spk.SearchIndex`; Typesense, behind the site's own search): its documents
carry the page but no Spektrix id, so the join is the event's exact name
(`spk.title_key`: "ILFORD BOY" = "Ilford Boy"). The site itself challenges
the production server's IP (Cloudflare). Links only, not curation: an
event the index doesn't name links to the Spektrix event page.
"""

from __future__ import annotations

import logging

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

logger = logging.getLogger(__name__)

VENUE_SLUG = "donmar-warehouse"
CLIENT = spk.Client("donmarwarehouse")
INDEX = spk.SearchIndex("donmar_main_production", "https://www.donmarwarehouse.com")


def categorize(event: dict) -> list[str]:
    return ["theater"] if spk.attr(event, "Website") == "Performance" else []


class DonmarWarehouseScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        try:
            pages = spk.search_title_pages(spk.search_events(INDEX), INDEX)
        except Exception as exc:  # links only: the Spektrix page will do
            logger.warning("donmar: search index unavailable (%s); linking the Spektrix pages", exc)
            pages = {}
        return spk.scrape(CLIENT, categorize, url=lambda e: pages.get(spk.title_key(e["name"])))


register(
    scraper=DonmarWarehouseScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Donmar Warehouse",
        city_slug="london",
        address="41 Earlham Street, London WC2H 9LX",
        site_url="https://www.donmarwarehouse.com",
        instagram_url="https://www.instagram.com/donmarwarehouse",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
