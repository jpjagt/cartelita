"""Theatre503 (Battersea) — new writing.

Spektrix client `theatre503`, via the shared `_spektrix` helper (see
theatre503_SOURCE.md). The client has no genre/type attribute and its
website lists everything it sells, masterclasses included, so curation uses
the performance's seating plan (`/plans`: name + venue):

- plans named "Theatre503 Writers' Programme" carry the writers' programme
  (online and in-person masterclasses/courses) — dropped;
- plans of the client's other venues (Nine Elms, Battersea Power Station
  Cinema, "Workshop test") — dropped;
- everything else in the Theatre503 venue (main-house runs, short runs,
  Rapid Write Response nights) → theater.

Show pages on theatre503.com embed the event's full Spektrix id, so events
link to the venue's own page.
"""

from __future__ import annotations

from collections.abc import Callable

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "theatre503"
CLIENT = spk.Client("theatre503", "https://tickets.theatre503.com")
SITE = spk.Site("https://theatre503.com/whats-on/", r"https://theatre503\.com/whats-on/[^/]+/")
STAGE_VENUE = "Theatre503"
WRITERS_PROGRAMME = "Theatre503 Writers' Programme"


def categorize(event: dict) -> list[str]:
    return ["theater"]


def fetch_plans(http) -> dict[str, tuple[str, str]]:
    """Seating-plan id → (plan name, client venue name)."""
    venues = http.get(f"{CLIENT.api}/venues")
    venues.raise_for_status()
    venue_names = {v["id"]: v["name"] for v in venues.json()}
    plans = http.get(f"{CLIENT.api}/plans")
    plans.raise_for_status()
    return {
        p["id"]: (p.get("name") or "", venue_names.get((p.get("venue") or {}).get("id"), ""))
        for p in plans.json()
    }


def venue_for(plans: dict[str, tuple[str, str]]) -> Callable[[dict, dict], str | None]:
    def venue(event: dict, instance: dict) -> str | None:
        plan_name, venue_name = plans.get(instance.get("planId") or "", ("", ""))
        if venue_name != STAGE_VENUE or plan_name.strip() == WRITERS_PROGRAMME:
            return None
        return VENUE_SLUG

    return venue


class Theatre503Scraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with spk.http_client() as http:
            plans = fetch_plans(http)
        return spk.scrape(CLIENT, categorize, site=SITE, venue=venue_for(plans))


register(
    scraper=Theatre503Scraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Theatre503",
        city_slug="london",
        address="The Latchmere, 503 Battersea Park Road, London SW11 3BW",
        site_url="https://theatre503.com",
        instagram_url="https://www.instagram.com/theatre503",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
