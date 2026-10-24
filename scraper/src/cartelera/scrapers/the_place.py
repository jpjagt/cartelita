"""The Place (Euston) — London's home of contemporary dance.

Spektrix client `theplace`, via the shared `_spektrix` helper (see
the_place_SOURCE.md). The box office also sells the dance school's classes,
courses, open days and info sessions, so curation combines three of the
client's own labels:

- `WebsiteListing` = "Performance" (not Class / Children and Youth Dance);
- `Type` (a programme label followed by a finance code) = Theatre Programme,
  Family Programme (→ dance + kids), Resolution (the festival) or LCDS
  FRAMERUSH (the school's public shows; its info sessions are Class) — not
  Resolution Workshops, LCDS ad-hoc Workshops (open/experience days) or
  Theatre External Hire;
- `WebsiteVenue` = "at The Place" (not off-site);

and drops touch tours, which carry all of the above but are ticketed as
`TicketName1` = "TOUCH TOUR".

Show pages on theplace.org.uk (book links `/book/instance/<numeric id>`)
are joined in for the event link.

Prices: each price list has a "Standard" band next to concession bands
("LCDS Student" £5, "Wheelchair spaces") that are flagged band-default too,
so the shared price rule would show "£5–22" where the venue says "Standard
£22, concs £18". This module prices from the Standard band only (the shared
rule when a price list has no Standard band).
"""

from __future__ import annotations

import re

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "the-place"
CLIENT = spk.Client("theplace")
SITE = spk.Site("https://theplace.org.uk/whats-on/", r"https://theplace\.org\.uk/events/[^/]+/?")

# `Type` label (finance code stripped) → our categories.
TYPES: dict[str, list[str]] = {
    "Theatre Programme": ["dance"],
    "Family Programme": ["dance", "kids"],
    "Resolution": ["dance"],
    "LCDS FRAMERUSH": ["dance"],
}
# Internal season prefixes on event names: "Autumn/ Winter 26: ",
# "Spring/Summer 2027: ".
_SEASON = re.compile(r"^(?:Autumn|Spring)\s*/\s*(?:Winter|Summer)\s*\d{2,4}\s*:\s*", re.I)


def type_label(event: dict) -> str:
    """"Theatre Programme - 99A 8054" → "Theatre Programme";
    "Resolution Workshops –1420 10B" → "Resolution Workshops"."""
    return re.sub(r"\s*[-–]?\s*\d.*$", "", spk.attr(event, "Type")).strip()


def categorize(event: dict) -> list[str]:
    if spk.attr(event, "WebsiteListing") != "Performance":
        return []
    if spk.attr(event, "WebsiteVenue") != "at The Place":
        return []
    if spk.attr(event, "TicketName1").upper() == "TOUCH TOUR":
        return []
    return list(TYPES.get(type_label(event), []))


def title(event: dict) -> str:
    return _SEASON.sub("", re.sub(r"\s+", " ", event["name"]).strip())


def standard_band(price: dict) -> bool:
    return spk.band(price) == "Standard"


class ThePlaceScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, site=SITE, title=title, price_bands=standard_band)


register(
    scraper=ThePlaceScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="The Place",
        city_slug="london",
        address="17 Duke's Road, London WC1H 9PY",
        site_url="https://theplace.org.uk",
        instagram_url="https://www.instagram.com/theplacelondon",
        category_slugs=["dance", "kids"],
        list_memberships=[
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
