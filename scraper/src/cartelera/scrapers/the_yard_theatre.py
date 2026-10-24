"""The Yard Theatre (Hackney Wick) — new work.

Spektrix client `theyard`, via the shared `_spektrix` helper (see
the_yard_theatre_SOURCE.md). The client has no genre/type attribute, so
curation uses the box office's own `webUrl` field: the Yard fills it with the
event's page on theyardtheatre.co.uk for every public show (runs and Live
Drafts) and leaves it empty for what it sells but doesn't programme (the Lear
gala fundraiser, "Name a Seat" and the like). The show pages embed no
Spektrix instance ids (their Next.js data carries short codes such as
"LEAR"), so no Site join is possible — `webUrl` is the link anyway.
"""

from __future__ import annotations

import re

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "the-yard-theatre"
CLIENT = spk.Client("theyard")
SHOW_PAGE = re.compile(r"https://(?:www\.)?theyardtheatre\.co\.uk/events/[^/?#]+/?")


def categorize(event: dict) -> list[str]:
    return ["theater"] if SHOW_PAGE.fullmatch((event.get("webUrl") or "").strip()) else []


class TheYardTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize)


register(
    scraper=TheYardTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="The Yard Theatre",
        city_slug="london",
        address="2a Queen's Yard, White Post Lane, London E9 5EN",
        site_url="https://www.theyardtheatre.co.uk",
        instagram_url="https://www.instagram.com/yardtheatre",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
