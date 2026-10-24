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

Show pages on theplace.org.uk book each performance as
`/book/instance/<numeric id>`, a link shape the shared Site join doesn't
recognise yet, so this module joins them itself (same matching rule:
`spk.site_urls`).

Prices: each price list has a "Standard" band next to concession bands
("LCDS Student" £5, "Wheelchair spaces") that are flagged band-default too,
so the shared price rule would show "£5–22" where the venue says "Standard
£22, concs £18". This module prices from the Standard band only.
"""

from __future__ import annotations

import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor

import httpx

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "the-place"
CLIENT = spk.Client("theplace")
SITE_LISTING = "https://theplace.org.uk/whats-on/"
SITE_LINK = r"https://theplace\.org\.uk/events/[^/]+/?"
_BOOK_INSTANCE = re.compile(r"/book/instance/(\d{4,8})\b")

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


def site_page_ids() -> dict[str, set[str]]:
    """Show-page URL → the numeric Spektrix instance ids it books."""
    listing = fetch(SITE_LISTING, headers=CARTELITA_BROWSER_HEADERS)
    links = list(dict.fromkeys(
        m.group(0) for m in re.finditer(r"https?://[^\s\"'<>#?]+", listing)
        if re.fullmatch(SITE_LINK, m.group(0))
    ))

    def ids(url: str) -> tuple[str, set[str]]:
        page = fetch(url, headers=CARTELITA_BROWSER_HEADERS)
        return url, set(_BOOK_INSTANCE.findall(page))

    with ThreadPoolExecutor(max_workers=spk.MAX_CONCURRENCY) as pool:
        return dict(pool.map(ids, links))


def price_text(price_list: dict) -> str | None:
    """The Standard band's price (concession bands left out); the shared
    rule when a price list has no Standard band."""
    standard = [
        p for p in price_list.get("prices") or []
        if ((p.get("priceBand") or {}).get("name") or "").strip() == "Standard"
    ]
    return spk.price_text({"prices": standard} if standard else price_list)


def fetch_prices(instances: list[dict], http: httpx.Client) -> dict[str, str | None]:
    """Price text per price-list id, as `spk.fetch_prices` (on-sale
    instances first, up to PRICE_ATTEMPTS each; failures = unknown) but with
    this venue's band rule."""
    candidates: dict[str, list[str]] = {}
    for inst in sorted(instances, key=lambda i: not i.get("isOnSale")):
        pl = (inst.get("priceList") or {}).get("id")
        if pl and len(ids := candidates.setdefault(pl, [])) < spk.PRICE_ATTEMPTS:
            ids.append(inst["id"])

    def one(item: tuple[str, list[str]]) -> tuple[str, str | None]:
        pl, inst_ids = item
        for inst_id in inst_ids:
            try:
                resp = http.get(f"{CLIENT.api}/instances/{inst_id}/price-list")
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                return pl, price_text(resp.json())
            except (httpx.HTTPError, ValueError):
                return pl, None
        return pl, None

    with ThreadPoolExecutor(max_workers=spk.MAX_CONCURRENCY) as pool:
        return dict(pool.map(one, candidates.items()))


class ThePlaceScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with spk.http_client() as http:
            events, instances = spk.fetch_programme(CLIENT, dt.date.today(), http)
            pages = spk.site_urls(site_page_ids(), events, instances)
            selected = spk.select(events, instances, categorize)
            prices = fetch_prices([inst for _e, inst, _c in selected], http)
        return spk.build(CLIENT, selected, prices, title=title, url=lambda e: pages.get(e["id"]))


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
