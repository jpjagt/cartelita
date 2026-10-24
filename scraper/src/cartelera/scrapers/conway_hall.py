"""Conway Hall (Holborn) — the Sunday Concerts, Europe's longest-running
chamber music series (since 1887), in the Main Hall.

Ticketsolve feed `conwayhall.ticketsolve.com/shows.xml` via the shared
`_ticketsolve` helper (see conway_hall_SOURCE.md). The hall's box office
also sells Conway Hall Ethical Society talks, venue hires (Intelligence
Squared), film nights and outside promoters' concerts; only the series
itself is ours: `event_category` = "Sunday Concerts" → classical. Every
other category (Talks & Debates, Film & Performance, Music — hires such as
candlelit carols — and uncategorised items, incl. the RNCM lunchtime
recitals) is dropped.
"""

from __future__ import annotations

from cartelera.scrapers import _ticketsolve as ts
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "conway-hall"
FEED_URL = "https://conwayhall.ticketsolve.com/shows.xml"
SERIES = "Sunday Concerts"


def keep(show: ts.Show, perf: ts.Performance) -> list[str]:
    return ["classical"] if show.category == SERIES else []


class ConwayHallScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return ts.scrape(FEED_URL, keep)


register(
    scraper=ConwayHallScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Conway Hall",
        city_slug="london",
        address="25 Red Lion Square, London WC1R 4RL",
        site_url="https://conwayhall.org.uk/sunday-concerts/",
        instagram_url="https://www.instagram.com/conwayhall",
        category_slugs=["classical"],
        list_memberships=[ListMembership(list_slug="classical")],
    ),
)
