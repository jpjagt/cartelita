"""Royal Court Theatre (Sloane Square) — new writing.

Spektrix client `royalcourt` (custom domain tickets.royalcourttheatre.com),
via the shared `_spektrix` helper (see royal_court_theatre_SOURCE.md). The
client has no genre/type attribute, so curation is two structural signals:

- the venue's own website (`Site(required=True)`): only events whose
  performances a royalcourttheatre.com show page embeds are kept. That drops
  the box office's test events ("Poppy Test Event", "Z - 2627 Test", "Touch
  Tour - TEST"), the per-show touch tours and anything not yet published;
- `TicketVenue1`, the room: only the two auditoriums (Jerwood Theatre
  Downstairs / Upstairs). The site also lists Balcony Bar / Bar & Kitchen
  talks and writers' sessions (Book Club, First Words, Writers' Card),
  backstage tours (the whole building), Zoom sessions and off-site parties
  and screenings — none of them performances.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "royal-court-theatre"
CLIENT = spk.Client("royalcourt", "https://tickets.royalcourttheatre.com")
# The sitemap lists every published show page (the what's-on page drops a
# show on its last day); show pages embed their performances' full Spektrix
# ids (booking buttons).
SITE = spk.Site(
    "https://royalcourttheatre.com/sitemap.xml",
    r"https://royalcourttheatre\.com/events/[a-z0-9-]+/?",
    required=True,
)
ROOMS = {"Jerwood Theatre Downstairs", "Jerwood Theatre Upstairs"}


def categorize(event: dict) -> list[str]:
    return ["theater"] if spk.attr(event, "TicketVenue1") in ROOMS else []


class RoyalCourtTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, site=SITE)


register(
    scraper=RoyalCourtTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Royal Court Theatre",
        city_slug="london",
        address="Sloane Square, London SW1W 8AS",
        site_url="https://royalcourttheatre.com",
        instagram_url="https://www.instagram.com/royalcourttheatre",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
