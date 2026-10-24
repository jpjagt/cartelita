"""Camden People's Theatre (Euston) — fringe, devised and new work.

Spektrix client `camdenpeoplestheatre`, via the shared `_spektrix` helper
(see camden_peoples_theatre_SOURCE.md). The client has no artform/type
attribute (only `FinancialArrangement`: Guarantee / Box office split /
External hire / Fee, all public shows) — and needs none: this box office
sells performances only (no ice-creams, programmes, tours or courses in the
2026 data), so every performance in the building is programme → theater.
The building comes from the performance's seating plan: the client also
sells shows at partner venues (The Place, Conway Hall, Soho Theatre, Rich
Mix… for its festivals) and online — only "Camden People's Theatre" is kept.

Show pages on cptheatre.co.uk are joined in for the event link (not for
curation: a page shows ticket links only while a performance is on sale, so
a required join would drop every sold-out show); its pages link
performances as `/tickets/<numeric instance id>`.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "camden-peoples-theatre"
CLIENT = spk.Client("camdenpeoplestheatre", "https://tickets.cptheatre.co.uk")
SITE = spk.Site("https://cptheatre.co.uk/Whats-On", r"https://cptheatre\.co\.uk/whatson/[^/]+")
STAGE_VENUE = "Camden People's Theatre"


def categorize(event: dict) -> list[str]:
    return ["theater"]


def venue(event: dict, instance: dict) -> str | None:
    return VENUE_SLUG if (instance.get("venue") or {}).get("name") == STAGE_VENUE else None


class CamdenPeoplesTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, site=SITE, venue=venue, plan_venues=True)


register(
    scraper=CamdenPeoplesTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Camden People's Theatre",
        city_slug="london",
        address="58-60 Hampstead Road, London NW1 2PY",
        site_url="https://cptheatre.co.uk",
        instagram_url="https://www.instagram.com/cptheatre",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
