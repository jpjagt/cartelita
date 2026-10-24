"""Park Theatre (Finsbury Park) — new writing in two auditoria (Park200,
Park90) and the Morris Space.

Spektrix client `parktheatre`, via the shared `_spektrix` helper (see
park_theatre_SOURCE.md). Curation uses the box office's own attributes:

- `Genre` — Drama, Musicals, Comedy (comic plays; stand-up has its own
  genre) and One-off events are programme; "Supplementary event" (pizzas,
  drinks, programmes, cast albums, touch tours, headsets, captioning) and
  "Stand-up comedy" are not (Cartelita has no comedy category);
- `Venue` — the room: Park200 / Park90 / Morris Space are the building;
  "Events Elsewhere" and "Online Event" are dropped;
- `RecommendationCategory1` (the event's primary recommendation label) =
  "Family" → kids; everything else → theater.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "park-theatre"
CLIENT = spk.Client("parktheatre", "https://tickets.parktheatre.co.uk")
# Show pages embed their performances' full Spektrix ids (booking buttons).
SITE = spk.Site("https://parktheatre.co.uk/whats-on/", r"https://parktheatre\.co\.uk/events/[^/]+/")

PROGRAMME_GENRES = {"Drama", "Musicals", "Comedy", "One-off events"}
ROOMS = {"Park200", "Park90", "Morris Space"}


def categorize(event: dict) -> list[str]:
    if spk.attr(event, "Genre") not in PROGRAMME_GENRES or spk.attr(event, "Venue") not in ROOMS:
        return []
    return ["kids"] if spk.attr(event, "RecommendationCategory1") == "Family" else ["theater"]


class ParkTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, site=SITE)


register(
    scraper=ParkTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Park Theatre",
        city_slug="london",
        address="Clifton Terrace, London N4 3JP",
        site_url="https://parktheatre.co.uk",
        instagram_url="https://www.instagram.com/parktheatre",
        category_slugs=["theater", "kids"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
