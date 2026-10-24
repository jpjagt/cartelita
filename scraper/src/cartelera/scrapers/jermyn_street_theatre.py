"""Jermyn Street Theatre (St James's) — 70-seat studio theatre off
Piccadilly: revivals, new plays, one-off Sunday shows.

Ticketsolve feed `jermynstreettheatre.ticketsolve.com/shows.xml` via the
shared `_ticketsolve` helper (see jermyn_street_theatre_SOURCE.md). The feed
carries no `event_category`; every show in it at the venue "Jermyn Street
Theatre" plays the one auditorium → theater. (Checked 2026-10-25: the feed
holds only performances — main-house runs and one-off Sunday/late shows —
no workshops, gift vouchers or memberships.)
"""

from __future__ import annotations

from cartelera.scrapers import _ticketsolve as ts
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "jermyn-street-theatre"
FEED_URL = "https://jermynstreettheatre.ticketsolve.com/shows.xml"
FEED_VENUE = "Jermyn Street Theatre"


def keep(show: ts.Show, perf: ts.Performance) -> list[str]:
    return ["theater"] if show.venue == FEED_VENUE else []


class JermynStreetTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return ts.scrape(FEED_URL, keep)


register(
    scraper=JermynStreetTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Jermyn Street Theatre",
        city_slug="london",
        address="16b Jermyn Street, London SW1Y 6ST",
        site_url="https://www.jermynstreettheatre.co.uk",
        instagram_url="https://www.instagram.com/jermynstreettheatre",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
