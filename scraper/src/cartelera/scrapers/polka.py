"""Polka Theatre (Wimbledon) — London's theatre for children.

Spektrix client `polka`, via the shared `_spektrix` helper (see
polka_SOURCE.md). The box office's own `Type` attribute separates shows from
everything else it sells: "Show" is programme; Holiday/Drop-in/School
Workshops, Saturday Club, Ancillary Event (ice-cream pre-orders) and Other
("Secure My Booking", touch tours, CPD days) are not.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "polka-theatre"
CLIENT = spk.Client("polka")
# Show pages embed their performances' full Spektrix ids (booking buttons).
SITE = spk.Site("https://polkatheatre.com/whats-on/", r"https://polkatheatre\.com/event/[^/]+/")


def categorize(event: dict) -> list[str]:
    return ["kids"] if spk.attr(event, "Type") == "Show" else []


class PolkaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, site=SITE)


register(
    scraper=PolkaScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Polka Theatre",
        city_slug="london",
        address="240 The Broadway, London SW19 1SB",
        site_url="https://polkatheatre.com",
        instagram_url="https://www.instagram.com/polkatheatre",
        category_slugs=["kids"],
        list_memberships=[ListMembership(list_slug="kids")],
    ),
)
