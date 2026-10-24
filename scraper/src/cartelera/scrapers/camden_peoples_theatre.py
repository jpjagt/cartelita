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
a required join would drop every sold-out show).

Helper gap: CPT's show pages link performances as `/tickets/<numeric
instance id>`, a form `_spektrix.site_page_ids` doesn't recognise, so this
module collects the page ids itself and runs the helper's steps directly
(the same steps as `_spektrix.scrape` with `plan_venues=True`).
"""

from __future__ import annotations

import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "camden-peoples-theatre"
CLIENT = spk.Client("camdenpeoplestheatre", "https://tickets.cptheatre.co.uk")
LISTING_URL = "https://cptheatre.co.uk/Whats-On"
SHOW_PAGE = r"https://cptheatre\.co\.uk/whatson/[^/]+"
TICKET_LINK = re.compile(r"/tickets/(\d{4,8})\b")
STAGE_VENUE = "Camden People's Theatre"


def categorize(event: dict) -> list[str]:
    return ["theater"]


def venue(event: dict, instance: dict) -> str | None:
    return VENUE_SLUG if (instance.get("venue") or {}).get("name") == STAGE_VENUE else None


def page_ids(html: str) -> set[str]:
    """The numeric Spektrix ids a show page links ("/tickets/351844")."""
    return {m.group(1) for m in TICKET_LINK.finditer(html)}


def site_page_ids() -> dict[str, set[str]]:
    """Show-page URL → the numeric Spektrix ids found on it."""
    listing = fetch(LISTING_URL, headers=CARTELITA_BROWSER_HEADERS)
    links = list(dict.fromkeys(
        m.group(0) for m in re.finditer(r"https?://[^\s\"'<>#?]+", listing)
        if re.fullmatch(SHOW_PAGE, m.group(0))
    ))

    def one(url: str) -> tuple[str, set[str]]:
        return url, page_ids(fetch(url, headers=CARTELITA_BROWSER_HEADERS))

    with ThreadPoolExecutor(max_workers=spk.MAX_CONCURRENCY) as pool:
        return dict(pool.map(one, links))


class CamdenPeoplesTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self, today: dt.date | None = None) -> list[ScrapedEvent]:
        today = today or dt.date.today()
        with spk.http_client() as http:
            events, instances = spk.fetch_programme(CLIENT, today, http)
            pages = spk.site_urls(site_page_ids(), events, instances)
            by_plan = spk.fetch_plan_venues(CLIENT, instances, http)
            for inst in instances:
                inst["venue"] = by_plan.get(inst.get("planId"), {})
            selected = spk.select(events, instances, categorize, venue)
            prices = spk.fetch_prices(CLIENT, [inst for _e, inst, _c in selected], http)
        return spk.build(CLIENT, selected, prices, url=lambda e: pages.get(e["id"]), venue=venue)


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
