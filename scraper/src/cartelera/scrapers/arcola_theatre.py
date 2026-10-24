"""Arcola Theatre (Dalston) — fringe and international theatre, plus its
summer opera festival, Grimeborn.

Spektrix client `arcolatheatre`, via the shared `_spektrix` helper (see
arcola_theatre_SOURCE.md). Curation uses the box office's own data:

- `Genre` — "Theatre" is programme; "Workshop" (writing workshops, youth
  theatre terms) is not;
- the performance's seating plan → the client's venue: only "Arcola Theatre"
  (Studios 1 and 2). The "Workshops" venue carries the participation strand
  (Arcola Youth Theatre terms, 50+ Serious Play — some coded Genre=Theatre),
  so it is dropped with the other non-stage venues;
- `Festival` = "Grimeborn" → classical (opera); everything else → theater.

Event names carry an internal season prefix ("2026: The Master Builder"),
stripped from titles.
"""

from __future__ import annotations

import re

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "arcola-theatre"
CLIENT = spk.Client("arcolatheatre", "https://boxoffice.arcolatheatre.com")
# Show pages embed their performances' full Spektrix ids (booking buttons).
SITE = spk.Site(
    "https://www.arcolatheatre.com/whats-on/",
    r"https://www\.arcolatheatre\.com/event/[^/]+/",
)
# The client's own venue name for the building's two studios.
STAGE_VENUE = "Arcola Theatre"


def categorize(event: dict) -> list[str]:
    if spk.attr(event, "Genre") != "Theatre":
        return []
    return ["classical"] if spk.attr(event, "Festival") == "Grimeborn" else ["theater"]


def venue(event: dict, instance: dict) -> str | None:
    return VENUE_SLUG if (instance.get("venue") or {}).get("name") == STAGE_VENUE else None


def title(event: dict) -> str:
    """"2026: The Master Builder" → "The Master Builder"."""
    name = re.sub(r"\s+", " ", event["name"]).strip()
    return re.sub(r"^\d{4}:\s*", "", name)


class ArcolaTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, site=SITE, title=title, venue=venue, plan_venues=True)


register(
    scraper=ArcolaTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Arcola Theatre",
        city_slug="london",
        address="24 Ashwin Street, London E8 3DL",
        site_url="https://www.arcolatheatre.com",
        instagram_url="https://www.instagram.com/arcolatheatre",
        category_slugs=["theater", "classical"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="classical", whitelist_category_slug="classical"),
        ],
    ),
)
