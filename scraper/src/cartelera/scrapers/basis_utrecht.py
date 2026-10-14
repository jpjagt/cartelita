from __future__ import annotations

import re

from bs4 import BeautifulSoup

from cartelera.scrapers import _tribe_events as tribe
from cartelera.scrapers import register
from cartelera.scrapers._eur import eur_amounts, format_eur
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# BASIS (Oudegracht aan de Werf 97, Utrecht) — basement techno/house club in a
# canal wharf cellar. WordPress + The Events Calendar; we read its REST API
# (see _tribe_events.py and basis_utrecht_SOURCE.md). The Tribe cost field is
# empty; the ticket tiers are typed in the description:
#   "/ Early entry before 23:30 €15" · "/ Doorsale entry after 23:30 €20"
# → we show the highest stated amount (the door price).
SITE_URL = "https://clubbasis.nl"
VENUE_SLUG = "basis-utrecht"

# The venue's catch-all category. An event labelled ONLY "Other" carries no
# music genre — it's a side activity (e.g. a free production class), not a
# club night. "Other" next to a genre (a listening session tagged
# "Experimental") is kept.
OTHER = "Other"

_TIER_LINE = re.compile(r"(?:entry|doorsale|door|ticket|presale|pre-sale)[^\n€]*€", re.IGNORECASE)


def is_programme(categories: list[str]) -> bool:
    return set(categories) != {OTHER}


def description_price(description_html: str | None) -> str | None:
    """Highest €-amount on a ticket-tier line ("/ Doorsale entry after 23:30
    €20") of the description; None when no tier line states an amount."""
    if not description_html:
        return None
    soup = BeautifulSoup(description_html, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    amounts: list[float] = []
    for line in soup.get_text("\n").split("\n"):
        if _TIER_LINE.search(line):
            amounts.extend(eur_amounts(line))
    return format_eur(max(amounts)) if amounts else None


def parse_events(raw: list[dict]) -> list[ScrapedEvent]:
    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for ev in raw:
        title = tribe.title(ev)
        if not title or not ev.get("url"):
            continue
        categories = tribe.category_names(ev)
        if not is_programme(categories):
            continue
        external_id = str(ev["id"])
        if external_id in seen:
            continue
        seen.add(external_id)
        start_date, start_time = tribe.start(ev)
        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=ev["url"],
                category_slugs=["club"],
                price=tribe.cost_price(ev) or description_price(ev.get("description")),
                image_url=tribe.image_url(ev),
                external_id=external_id,
                annotations=[c for c in categories if c != OTHER],
            )
        )
    return events


class BasisUtrechtScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return parse_events(tribe.fetch_all(SITE_URL))


register(
    scraper=BasisUtrechtScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="BASIS",
        city_slug="utrecht",
        address="Oudegracht aan de Werf 97, 3511 AL Utrecht",
        site_url=SITE_URL,
        instagram_url="https://www.instagram.com/clubbasis",
        category_slugs=["club"],
        list_memberships=[
            ListMembership(list_slug="club", whitelist_category_slug="club"),
        ],
    ),
)
