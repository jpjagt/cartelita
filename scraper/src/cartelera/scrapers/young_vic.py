"""Young Vic (The Cut, Waterloo).

Spektrix client `youngvic`, via the shared `_spektrix` helper (see
young_vic_SOURCE.md). Curation uses the box office's own attributes:

- `SupplementaryEvent` = true marks ancillaries (programmes, playtexts,
  assisted-listening and audio-description headsets, touch tours) — dropped;
- `Venue`, the room: Main House, The Maria Theatre, The Clare, and "Outside
  the Young Vic" (site-specific shows in the forecourt) are programme. An
  event without a room (the "Temporary Priority Test" box-office test) is
  dropped.

No site join: youngvic.org's show pages load their performances from the
site's own API (no Spektrix ids in the HTML) and link shows relatively, so
events link to the client's Spektrix event page.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "young-vic"
CLIENT = spk.Client("youngvic")
ROOMS = {"Main House", "The Maria Theatre", "The Clare", "Outside the Young Vic"}


def categorize(event: dict) -> list[str]:
    if event.get("attribute_SupplementaryEvent") is True:
        return []
    return ["theater"] if spk.attr(event, "Venue") in ROOMS else []


class YoungVicScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize)


register(
    scraper=YoungVicScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Young Vic",
        city_slug="london",
        address="66 The Cut, London SE1 8LZ",
        site_url="https://www.youngvic.org",
        instagram_url="https://www.instagram.com/youngvictheatre",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
