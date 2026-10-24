"""Donmar Warehouse (Covent Garden).

Spektrix client `donmarwarehouse`, via the shared `_spektrix` helper (see
donmar_warehouse_SOURCE.md). The box office's `Website` attribute:
"Performance" is programme; "Development event" (script conversations, the
"Supercool Test Event") is not.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "donmar-warehouse"
CLIENT = spk.Client("donmarwarehouse")
# Show pages embed their performances' full Spektrix ids.
SITE = spk.Site(
    "https://www.donmarwarehouse.com/whats-on/",
    r"https://www\.donmarwarehouse\.com/events/[a-z0-9-]+",
)


def categorize(event: dict) -> list[str]:
    return ["theater"] if spk.attr(event, "Website") == "Performance" else []


class DonmarWarehouseScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, site=SITE)


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
