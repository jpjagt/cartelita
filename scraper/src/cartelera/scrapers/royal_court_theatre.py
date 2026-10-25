"""Royal Court Theatre (Sloane Square) — new writing.

Spektrix client `royalcourt` (custom domain tickets.royalcourttheatre.com),
via the shared `_spektrix` helper (see royal_court_theatre_SOURCE.md). The
client has no genre/type attribute, so curation is two structural signals:

- listed on the venue's own website: only events the site's search index
  (`spk.SearchIndex`, the Typesense index behind royalcourttheatre.com's
  what's-on and search) lists are kept. Its documents carry no Spektrix id,
  so the join is the event's exact name (`spk.title_key`: case and spacing
  only, never fuzzy). That drops the box office's test events ("Poppy Test
  Event", "Z - 2627 Test", "Touch Tour - TEST"), the per-show touch tours
  ("The Afronauts - Touch Tour") and anything not yet published. (The site
  itself challenges the production server's IP — Cloudflare — so its
  sitemap and show pages can't be the join there.);
- `TicketVenue1`, the room: only the two auditoriums (Jerwood Theatre
  Downstairs / Upstairs). The site also lists Balcony Bar / Bar & Kitchen
  talks and writers' sessions (Book Club, First Words, Writers' Card),
  backstage tours (the whole building), Zoom sessions and off-site parties
  and screenings — none of them performances.

Prices leave out the "Standing" band: the Jerwood Downstairs' 10p standing
tickets (sold on the day) are a real ticket, but the theatre's own price
statement ("Tickets: £15 - £74.50") leaves them out, and a "£0.10–74.50"
range would misstate what a seat costs.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "royal-court-theatre"
CLIENT = spk.Client("royalcourt", "https://tickets.royalcourttheatre.com")
INDEX = spk.SearchIndex("royalcourttheatre_main_production", "https://royalcourttheatre.com")
ROOMS = {"Jerwood Theatre Downstairs", "Jerwood Theatre Upstairs"}
STANDING_BAND = "Standing"


def categorize(event: dict) -> list[str]:
    return ["theater"] if spk.attr(event, "TicketVenue1") in ROOMS else []


def seated_band(price: dict) -> bool:
    return spk.band(price) != STANDING_BAND


class Listing:
    """Curation and page link from the site's listed events (name → page)."""

    def __init__(self, pages: dict[str, str]):
        self.pages = pages

    def categorize(self, event: dict) -> list[str]:
        return categorize(event) if self.url(event) else []

    def url(self, event: dict) -> str | None:
        return self.pages.get(spk.title_key(event["name"]))


class RoyalCourtTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        listing = Listing(spk.search_title_pages(spk.search_events(INDEX), INDEX))
        return spk.scrape(CLIENT, listing.categorize, url=listing.url, price_bands=seated_band)


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
