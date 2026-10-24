"""New Diorama Theatre (Regent's Place, Euston) — independent studio
theatre for ensembles and new companies.

Ticketsolve feed `newdiorama-tickets.newdiorama.com/shows.xml` via the
shared `_ticketsolve` helper (see new_diorama_theatre_SOURCE.md). The feed is
the theatre's own box office for its one 80-seat auditorium and carries no
`event_category`: every show in it at the venue "New Diorama Theatre" is a
production → theater. (Checked 2026-10-25: no ancillaries — no workshops,
memberships or vouchers — in the feed.)
"""

from __future__ import annotations

from cartelera.scrapers import _ticketsolve as ts
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "new-diorama-theatre"
FEED_URL = "https://newdiorama-tickets.newdiorama.com/shows.xml"
FEED_VENUE = "New Diorama Theatre"


def keep(show: ts.Show, perf: ts.Performance) -> list[str]:
    return ["theater"] if show.venue == FEED_VENUE else []


class NewDioramaTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return ts.scrape(FEED_URL, keep)


register(
    scraper=NewDioramaTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="New Diorama Theatre",
        city_slug="london",
        address="15-16 Triton Street, Regent's Place, London NW1 3BF",
        site_url="https://newdiorama.com",
        instagram_url="https://www.instagram.com/newdiorama",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
