"""Soho Theatre (Dean Street) and Soho Theatre Walthamstow.

One Spektrix client (`sohotheatre`) sells both buildings, so this is a
multi-venue source, via the shared `_spektrix` helper (see
soho_theatre_SOURCE.md). Curation uses the box office's own attributes:

- `Venue` — the room: Theatre / Upstairs / Downstairs / Studio 1 are Dean
  Street, "Soho Theatre Walthamstow" is Walthamstow; anything else (the Soho
  Theatre Pub, the Glasgow Glee Club, blank) is dropped;
- `WebsiteFilterCategory1` — the website's own filter: Theatre → theater,
  Family → kids. Comedy, Cabaret, Music and Podcast (most of the volume) are
  out of scope for now: Cartelita has no comedy category.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register_source
from cartelera.types import ListMembership, ScrapedEvent, SourceDefinition, VenueDefinition

SOURCE_SLUG = "soho-theatre"
DEAN_STREET = "soho-theatre"
WALTHAMSTOW = "soho-theatre-walthamstow"
CLIENT = spk.Client("sohotheatre")

ROOMS: dict[str, str] = {
    "Theatre": DEAN_STREET,
    "Upstairs": DEAN_STREET,
    "Downstairs": DEAN_STREET,
    "Studio 1": DEAN_STREET,
    "Soho Theatre Walthamstow": WALTHAMSTOW,
}
CATEGORIES: dict[str, str] = {"Theatre": "theater", "Family": "kids"}


def room_venue(event: dict) -> str | None:
    return ROOMS.get(spk.attr(event, "Venue"))


def venue(event: dict, instance: dict) -> str | None:
    return room_venue(event)


def categorize(event: dict) -> list[str]:
    if room_venue(event) is None:
        return []
    cat = CATEGORIES.get(spk.attr(event, "WebsiteFilterCategory1"))
    return [cat] if cat else []


class SohoTheatreScraper:
    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, venue=venue)


_LISTS = [
    ListMembership(list_slug="theater", whitelist_category_slug="theater"),
    ListMembership(list_slug="kids", whitelist_category_slug="kids"),
]

register_source(
    SohoTheatreScraper(),
    SourceDefinition(
        slug=SOURCE_SLUG,
        name="Soho Theatre",
        venues=[
            VenueDefinition(
                slug=DEAN_STREET,
                name="Soho Theatre",
                city_slug="london",
                address="21 Dean Street, London W1D 3NE",
                site_url="https://sohotheatre.com",
                instagram_url="https://www.instagram.com/sohotheatre",
                category_slugs=["theater", "kids"],
                list_memberships=_LISTS,
            ),
            VenueDefinition(
                slug=WALTHAMSTOW,
                name="Soho Theatre Walthamstow",
                city_slug="london",
                address="186 Hoe Street, London E17 4QH",
                site_url="https://sohotheatre.com",
                instagram_url="https://www.instagram.com/sohotheatre",
                category_slugs=["theater", "kids"],
                list_memberships=_LISTS,
            ),
        ],
    ),
)
