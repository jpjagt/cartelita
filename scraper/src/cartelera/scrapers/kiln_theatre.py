"""Kiln Theatre (Kilburn) — theatre and its cinema.

Spektrix client `tricycle` (the old Tricycle Theatre's name), via the shared
`_spektrix` helper (see kiln_theatre_SOURCE.md). The box office's `Type`
attribute: "Theatre" → theater, "Cinema" → film (Kiln Cinema's screenings,
incl. NT Live and event cinema, belong to this source, not Clusterflick);
"Supplementary Event" (audio-description add-ons) and "External Hire" are
dropped. (`WebEventType` is not enough: the add-ons carry "Theatre" there.)

Show pages are joined from two listings — the what's-on page links the
theatre shows, the cinema-listings page the films — so this module runs the
helper's steps itself instead of `spk.scrape` (which takes one listing).
"""

from __future__ import annotations

import datetime as dt

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "kiln-theatre"
CLIENT = spk.Client("tricycle")
# Show pages link each performance as ".../book/<numeric instance id>".
_SHOW_PAGE = r"https://kilntheatre\.com/whats-on/[^/]+/"
SITES = (
    spk.Site("https://kilntheatre.com/whats-on/", _SHOW_PAGE),
    spk.Site("https://kilntheatre.com/cinema-listings/", _SHOW_PAGE),
)
TYPES: dict[str, str] = {"Theatre": "theater", "Cinema": "film"}


def categorize(event: dict) -> list[str]:
    cat = TYPES.get(spk.attr(event, "Type"))
    return [cat] if cat else []


class KilnTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with spk.http_client() as http:
            events, instances = spk.fetch_programme(CLIENT, dt.date.today(), http)
            page_ids: dict[str, set[str]] = {}
            for site in SITES:
                page_ids.update(spk.site_page_ids(site))
            pages = spk.site_urls(page_ids, events, instances)
            selected = spk.select(events, instances, categorize)
            prices = spk.fetch_prices(CLIENT, [inst for _e, inst, _c in selected], http)
        return spk.build(CLIENT, selected, prices, url=lambda event: pages.get(event["id"]))


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
