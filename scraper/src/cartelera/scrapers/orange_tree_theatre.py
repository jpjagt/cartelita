"""Orange Tree Theatre (Richmond) — rediscoveries and new writing in the
round.

Spektrix client `orangetree`, via the shared `_spektrix` helper (see
orange_tree_theatre_SOURCE.md). Curation uses the box office's own data:

- `Type` — "Classical Play" and "Drama New Writing" are programme →
  theater. Dropped: "Literary Talks" (Saturday Seminars), "Youth
  Theatre/Drama", "Children/Family" (schools' Primary Shakespeare),
  "Chamber & Recitals" (in this client, always the "Chamber Music at St
  Mary Magdalene" series — off-site, though booked on the theatre's plan)
  and untyped events (OT On Screen streams, short courses, workshops,
  seminars, coffee concerts);
- the performance's seating plan → the client's venue: only "Orange Tree
  Theatre" (OT in the Church at St John's, Thomas' College are dropped).

The show pages on orangetreetheatre.co.uk embed no Spektrix ids (their
booking widget loads client-side), so events link to the Spektrix event page.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "orange-tree-theatre"
CLIENT = spk.Client("orangetree", "https://tickets.orangetreetheatre.co.uk")
PLAY_TYPES = {"Classical Play", "Drama New Writing"}
STAGE_VENUE = "Orange Tree Theatre"


def categorize(event: dict) -> list[str]:
    return ["theater"] if spk.attr(event, "Type") in PLAY_TYPES else []


def venue(event: dict, instance: dict) -> str | None:
    return VENUE_SLUG if (instance.get("venue") or {}).get("name") == STAGE_VENUE else None


class OrangeTreeTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, venue=venue, plan_venues=True)


register(
    scraper=OrangeTreeTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Orange Tree Theatre",
        city_slug="london",
        address="1 Clarence Street, Richmond TW9 2SA",
        site_url="https://orangetreetheatre.co.uk",
        instagram_url="https://www.instagram.com/orangetreetheatre",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
