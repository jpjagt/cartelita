"""Little Angel Theatre (Dagmar Passage) and Little Angel Studios (Sebbon
Street), Islington — puppet theatre for children.

One Spektrix client (`littleangeltheatre`) sells both buildings, so this is a
multi-venue source, via the shared `_spektrix` helper (see
little_angel_theatre_SOURCE.md). Curation uses the box office's own data:

- `EventType` — "In-house show" (relaxed performances included) is
  programme; "Family activity" workshops, "Children only activity"
  playschemes and the adult courses are not;
- the performance's seating plan → the client's venue: "Little Angel
  Theatre" or "Little Angel Studios" (online/off-site venues are dropped).
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register_source
from cartelera.types import ListMembership, ScrapedEvent, SourceDefinition, VenueDefinition

SOURCE_SLUG = "little-angel-theatre"
THEATRE = "little-angel-theatre"
STUDIOS = "little-angel-studios"
CLIENT = spk.Client("littleangeltheatre")
# Show pages link each performance as ".../book/<numeric instance id>".
SITE = spk.Site(
    "https://www.littleangeltheatre.com/whats-on/",
    r"https://www\.littleangeltheatre\.com/whats-on/[^/]+/",
)
# The client's own venue names (`/venues`) → ours.
VENUES: dict[str, str] = {"Little Angel Theatre": THEATRE, "Little Angel Studios": STUDIOS}


def categorize(event: dict) -> list[str]:
    return ["kids"] if spk.attr(event, "EventType") == "In-house show" else []


def venue(event: dict, instance: dict) -> str | None:
    return VENUES.get((instance.get("venue") or {}).get("name", ""))


class LittleAngelTheatreScraper:
    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, site=SITE, venue=venue, plan_venues=True)


_COMMON = dict(
    city_slug="london",
    site_url="https://www.littleangeltheatre.com",
    instagram_url="https://www.instagram.com/littleangeltheatre",
    category_slugs=["kids"],
    list_memberships=[ListMembership(list_slug="kids")],
)

register_source(
    LittleAngelTheatreScraper(),
    SourceDefinition(
        slug=SOURCE_SLUG,
        name="Little Angel Theatre",
        venues=[
            VenueDefinition(slug=THEATRE, name="Little Angel Theatre",
                            address="14 Dagmar Passage, London N1 2DN", **_COMMON),
            VenueDefinition(slug=STUDIOS, name="Little Angel Studios",
                            address="Sebbon Street, London N1 2EH", **_COMMON),
        ],
    ),
)
