"""St Martin-in-the-Fields (Trafalgar Square) — church concerts: lunchtime
recitals, the Masterworks series, St Martin's Voices, the Crypt.

Spektrix client `stmartininthefields` on tickets.stmartin-in-the-fields.org,
via the shared `_spektrix` helper (see st_martin_in_the_fields_SOURCE.md).
Curation on the box office's own attributes:

- `Category` = Music and `SubCategories` — Masterworks, Lunchtime Concerts,
  Choral Discovery Concerts, Christmas, Easter Festival of Music, Sounds of
  St Martin's, Crypt Close-Up → classical; Family → classical + kids. NOT
  the church's own "Candlelight Concerts" tourist series (~50 events of
  Four Seasons / Mozart Requiem by Candlelight), Crypt Live (tribute and
  cabaret nights: Motown, Sinatra, Nashville, West End), Come and Sing
  (participatory), Contemporary, Silent Disco; and nothing of Lectures &
  Courses, Ancillary Sales (cushion hire, café meals) or Special Events;
- `Genre` must name a genre: the two Masterworks items with "Not
  Applicable" are a Streisand tribute and an Indian-music recital.

The website's listing is built by script (no show links in the HTML), so
events link to the Spektrix event page.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "st-martin-in-the-fields"
CLIENT = spk.Client("stmartininthefields", "https://tickets.stmartin-in-the-fields.org")

CLASSICAL = {
    "Masterworks",
    "Lunchtime Concerts",
    "Choral Discovery Concerts",
    "Christmas",
    "Easter Festival of Music",
    "Sounds of St Martin's",
    "Crypt Close-Up",
}
NO_GENRE = {"", "Not Applicable"}


def categorize(event: dict) -> list[str]:
    if spk.attr(event, "Category") != "Music" or spk.attr(event, "Genre") in NO_GENRE:
        return []
    sub = spk.attr(event, "SubCategories")
    if sub in CLASSICAL:
        return ["classical"]
    if sub == "Family":
        return ["classical", "kids"]
    return []


class StMartinInTheFieldsScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize)


register(
    scraper=StMartinInTheFieldsScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="St Martin-in-the-Fields",
        city_slug="london",
        address="Trafalgar Square, London WC2N 4JJ",
        site_url="https://www.stmartin-in-the-fields.org",
        instagram_url="https://www.instagram.com/stmartininthefields",
        category_slugs=["classical", "kids"],
        list_memberships=[
            ListMembership(list_slug="classical", whitelist_category_slug="classical"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
