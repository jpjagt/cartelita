"""Smith Square Hall (formerly St John's Smith Square), Westminster — run by
Sinfonia Smith Square.

Spektrix client `sinfoniasmithsquare` on checkout.sinfoniasmithsq.org.uk,
via the shared `_spektrix` helper (see sinfonia_smith_square_SOURCE.md).
Curation on the box office's own attributes:

- `Venue` — "Smith Square Hall" or "Smith Square Crypt" (the same building);
  concerts it sells elsewhere (Westminster Abbey) and items without a venue
  (the "post-show reception" upsell) are dropped;
- `Type` — Orchestral / Choral / Chamber / Organ / Vocal / Opera → classical,
  Jazz → jazz, "Family concerts and events" → classical + kids;
- `Series` — "Jazz in the Crypt" → jazz; an event without a `Type` but in
  one of the house's own series (Lunchtime Concerts, London Festival of
  Baroque Music, Christmas Festival…) → classical. Events with neither label
  are dropped (unlabelled external hires).

The website loads its performances by script (no Spektrix ids in the HTML),
so events link to the Spektrix event page.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "smith-square-hall"
CLIENT = spk.Client("sinfoniasmithsquare", "https://checkout.sinfoniasmithsq.org.uk")

VENUES = {"Smith Square Hall", "Smith Square Crypt"}
CLASSICAL_TYPES = {"Orchestral", "Choral", "Chamber", "Organ", "Vocal", "Opera"}
JAZZ_SERIES = "Jazz in the Crypt"


def categorize(event: dict) -> list[str]:
    if spk.attr(event, "Venue") not in VENUES:
        return []
    kind, series = spk.attr(event, "Type"), spk.attr(event, "Series")
    if kind == "Jazz" or series == JAZZ_SERIES:
        return ["jazz"]
    if kind in CLASSICAL_TYPES:
        return ["classical"]
    if kind == "Family concerts and events":
        return ["classical", "kids"]
    if not kind and series:
        return ["classical"]
    return []


class SinfoniaSmithSquareScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize)


register(
    scraper=SinfoniaSmithSquareScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Smith Square Hall",
        city_slug="london",
        address="Smith Square, London SW1P 3HA",
        site_url="https://www.sinfoniasmithsq.org.uk",
        instagram_url="https://www.instagram.com/sinfoniasmithsq",
        category_slugs=["classical", "jazz", "kids"],
        list_memberships=[
            ListMembership(list_slug="classical", whitelist_category_slug="classical"),
            ListMembership(list_slug="jazz", whitelist_category_slug="jazz"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
