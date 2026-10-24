"""Wigmore Hall (Marylebone) — London's chamber music and song hall.

The hall's own website API (Tessitura behind it) answers JSON to plain httpx:
`GET /api/v1/listings/whats-on?page=N` — every performance with `date`,
`url`, `title`, `subtitleText` (programme), `pricesText` ("£45 £38 £34 …",
"£18 (concessions £16)", "Free"), `tessituraId`, image. The listing items
carry no genre, but the API takes the what's-on page's own filters as query
parameters (a repeated parameter is a union), so curation = which of the
site's filters a performance answers to (see wigmore_hall_SOURCE.md):

- `genres` = chamber / choral / contemporary / early-music / global / piano /
  song / string-quartet → classical; `genres=jazz` → jazz (a performance in
  both gets both);
- `learningGenres=events-for-families` (family concerts, Chamber Tots,
  For Crying Out Loud!) → kids;
- the other Learning strands (`events-for-schools`, `music-for-the-moment`,
  `imagine-series`) are dropped, as is anything in no filter at all (a
  members' open rehearsal, a talk).
"""

from __future__ import annotations

import datetime as dt
import html
import re
from zoneinfo import ZoneInfo

import httpx

from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_COMPAT_UA
from cartelera.scrapers.price import gbp_price
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "wigmore-hall"
SITE = "https://www.wigmore-hall.org.uk"
API = f"{SITE}/api/v1/listings/whats-on"
LONDON = ZoneInfo("Europe/London")

CLASSICAL_GENRES = (
    "chamber", "choral", "contemporary", "early-music", "global", "piano", "song", "string-quartet",
)
# Our category (or "drop") → the what's-on filters that select it.
FILTERS: dict[str, list[tuple[str, str]]] = {
    "classical": [("genres", g) for g in CLASSICAL_GENRES],
    "jazz": [("genres", "jazz")],
    "kids": [("learningGenres", "events-for-families")],
    "drop": [("learningGenres", g) for g in ("events-for-schools", "music-for-the-moment", "imagine-series")],
}
CATEGORY_ORDER = ("classical", "jazz", "kids")
MAX_PAGES = 60


def fetch_filter(client: httpx.Client, params: list[tuple[str, str]]) -> list[dict]:
    """Every listing item (`node`) answering to `params`, all pages."""
    nodes: list[dict] = []
    page = 1
    while True:
        resp = client.get(API, params=[*params, ("page", str(page))])
        resp.raise_for_status()
        data = resp.json()
        nodes += [item["node"] for item in data.get("items") or []]
        if page >= (data.get("totalPages") or 0) or page >= MAX_PAGES:
            return nodes
        page += 1


def _text(value: str | None) -> str:
    """HTML fragment → plain text ("Selections from <em>Songs</em>")."""
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def price(prices_text: str | None) -> str | None:
    """`pricesText` → house convention. The `<sub>` small print ("+£1 booking
    fee per transaction") is not a ticket price."""
    text = _text(re.sub(r"(?is)<sub>.*?</sub>", " ", prices_text or ""))
    found = gbp_price(text)
    if found:
        return found
    return "free" if re.match(r"(?i)free\b", text) else None


def build(node: dict, categories: list[str]) -> ScrapedEvent:
    start = dt.datetime.fromisoformat(node["date"]).astimezone(LONDON)
    image = (node.get("listingImage") or {}).get("x2") or (node.get("listingImage") or {}).get("src")
    return ScrapedEvent(
        title=_text(node["title"]),
        start_date=start.date(),
        start_time=start.time().replace(tzinfo=None),
        source_url=SITE + node["url"],
        category_slugs=categories,
        price=price(node.get("pricesText")),
        description=_text(node.get("subtitleText")) or None,
        image_url=image or None,
        external_id=str(node.get("tessituraId") or node["url"]),
    )


def parse(listings: dict[str, list[dict]]) -> list[ScrapedEvent]:
    """Per filter group ("classical", "jazz", "kids", "drop") its listing
    items → one ScrapedEvent per performance, categorized by the groups it
    answers to; a performance in "drop" (or in none) is left out."""
    dropped = {n["url"] for n in listings.get("drop", [])}
    nodes: dict[str, dict] = {}
    cats: dict[str, list[str]] = {}
    for category in CATEGORY_ORDER:
        for node in listings.get(category, []):
            if node["url"] in dropped:
                continue
            nodes.setdefault(node["url"], node)
            if category not in cats.setdefault(node["url"], []):
                cats[node["url"]].append(category)
    events = [build(nodes[url], cats[url]) for url in nodes]
    return sorted(events, key=lambda e: (e.start_date, e.start_time or dt.time()))


class WigmoreHallScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        headers = {"User-Agent": CARTELITA_COMPAT_UA, "Accept": "application/json"}
        with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
            listings = {group: fetch_filter(client, params) for group, params in FILTERS.items()}
        return parse(listings)


register(
    scraper=WigmoreHallScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Wigmore Hall",
        city_slug="london",
        address="36 Wigmore Street, London W1U 2BP",
        site_url=SITE,
        instagram_url="https://www.instagram.com/wigmorehall",
        category_slugs=["classical", "jazz", "kids"],
        list_memberships=[
            ListMembership(list_slug="classical", whitelist_category_slug="classical"),
            ListMembership(list_slug="jazz", whitelist_category_slug="jazz"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
