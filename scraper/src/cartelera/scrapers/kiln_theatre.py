"""Kiln Theatre (Kilburn) — theatre and its cinema.

Spektrix client `tricycle` (the old Tricycle Theatre's name), via the shared
`_spektrix` helper (see kiln_theatre_SOURCE.md). The box office's `Type`
attribute: "Theatre" → theater, "Cinema" → film (Kiln Cinema's screenings,
incl. NT Live and event cinema, belong to this source, not Clusterflick);
"Supplementary Event" (audio-description add-ons) and "External Hire" are
dropped. (`WebEventType` is not enough: the add-ons carry "Theatre" there.)

Show pages are joined from two listings — the what's-on page links the
theatre shows, the cinema-listings page the films. The performance's
`AccessPerformance` text ("Captioned Screening", "Relaxed Performance",
"Parent and Baby Screening"…) becomes an annotation.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "kiln-theatre"
CLIENT = spk.Client("tricycle")
# Show pages link each performance as ".../book/<numeric instance id>".
SITE = spk.Site(
    ("https://kilntheatre.com/whats-on/", "https://kilntheatre.com/cinema-listings/"),
    r"https://kilntheatre\.com/whats-on/[^/]+/",
)
TYPES: dict[str, str] = {"Theatre": "theater", "Cinema": "film"}


def categorize(event: dict) -> list[str]:
    cat = TYPES.get(spk.attr(event, "Type"))
    return [cat] if cat else []


class KilnTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, site=SITE, annotation_attrs=("AccessPerformance",))


register(
    scraper=KilnTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Kiln Theatre",
        city_slug="london",
        address="269 Kilburn High Road, London NW6 7JR",
        site_url="https://kilntheatre.com",
        instagram_url="https://www.instagram.com/kilntheatre",
        category_slugs=["theater", "film"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="film", whitelist_category_slug="film"),
        ],
    ),
)
