"""Bush Theatre (Shepherd's Bush) — new writing.

Spektrix client `bushtheatre` (custom domain tickets.bushtheatre.co.uk), via
the shared `_spektrix` helper (see bush_theatre_SOURCE.md). The box office's
`WebsiteCategorisation` attribute separates the season from everything else
it sells: "Production" is programme; "Supplementary" (pre-order drinks,
audio-description headsets, captioning facilities, touch tours) is not.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "bush-theatre"
CLIENT = spk.Client("bushtheatre", "https://tickets.bushtheatre.co.uk")
# Show pages embed their performances' full Spektrix ids.
SITE = spk.Site(
    "https://www.bushtheatre.co.uk/whats-on/",
    r"https://www\.bushtheatre\.co\.uk/event/[^/]+/",
)


def categorize(event: dict) -> list[str]:
    return ["theater"] if spk.attr(event, "WebsiteCategorisation") == "Production" else []


class BushTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, site=SITE)


register(
    scraper=BushTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Bush Theatre",
        city_slug="london",
        address="7 Uxbridge Road, London W12 8LJ",
        site_url="https://www.bushtheatre.co.uk",
        instagram_url="https://www.instagram.com/bushtheatre",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
