"""Unicorn Theatre (London Bridge) — the UK's largest theatre for children.

Spektrix client `unicorntheatre`, via the shared `_spektrix` helper (see
unicorn_theatre_SOURCE.md). Every event the box office sells is a show
(`EventType` Unicorn Production / Co-production / Visiting Company), so the
curation is per performance, on the instance attributes:

- `Owner` — "Public" and "Press Night" performances are sold to the public;
  "Schools" performances are booked by school groups only and are dropped;
- `Location` — "Unicorn Theatre (Weston)" / "Unicorn Theatre (Clore)", the
  two auditoria; anything else (the client also has a "Digital theatre in
  your home" venue) is dropped.

The website's show pages load their dates by script and embed no Spektrix
ids, so events link to the Spektrix event page.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "unicorn-theatre"
CLIENT = spk.Client("unicorntheatre")

EVENT_TYPES = {"Unicorn Production", "Co-production", "Visiting Company"}
PUBLIC_OWNERS = {"Public", "Press Night"}
AUDITORIA = {"Unicorn Theatre (Weston)", "Unicorn Theatre (Clore)"}


def categorize(event: dict) -> list[str]:
    return ["kids"] if spk.attr(event, "EventType") in EVENT_TYPES else []


def venue(event: dict, instance: dict) -> str | None:
    if spk.attr(instance, "Owner") not in PUBLIC_OWNERS:
        return None
    if spk.attr(instance, "Location") not in AUDITORIA:
        return None
    return VENUE_SLUG


class UnicornTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, venue=venue)


register(
    scraper=UnicornTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Unicorn Theatre",
        city_slug="london",
        address="147 Tooley Street, London SE1 2HZ",
        site_url="https://www.unicorntheatre.com",
        instagram_url="https://www.instagram.com/unicorn_theatre",
        category_slugs=["kids"],
        list_memberships=[ListMembership(list_slug="kids")],
    ),
)
