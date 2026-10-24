"""Southwark Playhouse — two buildings: Borough (Newington Causeway) and
Elephant (Elephant Park).

One Spektrix client (`southwarkplayhouse`) sells both, so this is a
multi-venue source, via the shared `_spektrix` helper (see
southwark_playhouse_SOURCE.md). The client has no genre/type attribute, so
curation is the venue's own website: only events whose production page on
southwarkplayhouse.co.uk embeds their Spektrix id are kept
(`Site(required=True)`; e.g. the Black Writers Collective sessions are
sold but not listed). The building comes from the performance's seating plan
(`plan_venues=True`): the client's "Southwark Playhouse Borough" /
"Southwark Playhouse Elephant".
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register_source
from cartelera.types import ListMembership, ScrapedEvent, SourceDefinition, VenueDefinition

SOURCE_SLUG = "southwark-playhouse"
BOROUGH = "southwark-playhouse-borough"
ELEPHANT = "southwark-playhouse-elephant"
CLIENT = spk.Client("southwarkplayhouse")
# The homepage lists every production; each production page embeds the
# event's full Spektrix id (<var id="spektrixid">).
SITE = spk.Site(
    "https://southwarkplayhouse.co.uk/",
    r"https://southwarkplayhouse\.co\.uk/productions/[^/]+/",
    required=True,
)
VENUES: dict[str, str] = {
    "Southwark Playhouse Borough": BOROUGH,
    "Southwark Playhouse Elephant": ELEPHANT,
}


def categorize(event: dict) -> list[str]:
    return ["theater"]


def venue(event: dict, instance: dict) -> str | None:
    return VENUES.get((instance.get("venue") or {}).get("name", ""))


class SouthwarkPlayhouseScraper:
    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, site=SITE, venue=venue, plan_venues=True)


_COMMON = dict(
    city_slug="london",
    site_url="https://southwarkplayhouse.co.uk",
    instagram_url="https://www.instagram.com/swkplay",
    category_slugs=["theater"],
    list_memberships=[ListMembership(list_slug="theater")],
)

register_source(
    SouthwarkPlayhouseScraper(),
    SourceDefinition(
        slug=SOURCE_SLUG,
        name="Southwark Playhouse",
        venues=[
            VenueDefinition(slug=BOROUGH, name="Southwark Playhouse Borough",
                            address="77-85 Newington Causeway, London SE1 6BD", **_COMMON),
            VenueDefinition(slug=ELEPHANT, name="Southwark Playhouse Elephant",
                            address="1 Dante Place, London SE11 4RX", **_COMMON),
        ],
    ),
)
