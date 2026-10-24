"""Kings Place (King's Cross) — independent hall with classical, folk and
jazz series (Hall One, Hall Two, St Pancras Room).

Spektrix client `kingsplace` on ticketing.purchase.kingsplace.co.uk via the
shared `_spektrix` helper (see kings_place_SOURCE.md), joined to the
kingsplace.co.uk what's-on listing. The box office has no genre attribute
(only `Ticketsforgood…`/`ImportId`), but the website files every
performance under a genre, and each event page's URL carries it:
`/whats-on/classical/…`, `/whats-on/folk/…`, `/whats-on/jazz/…`. That path
is the curation:

- classical → classical, folk → folk, jazz → jazz;
- contemporary (Songlines world music), family, words, comedy, podcast,
  festival-only paths (origins-unwrapped…) are dropped, as are cards
  marked `online-events` (streams) and every Spektrix event the website
  doesn't list (test events, "Secure My Booking", the restaurant).

The listing (`/whats-on/`, paged `/whats-on/page/N/`; Cloudflare 403s httpx,
curl_cffi passes) renders one card per performance: `data-id` is the
Spektrix instance id (or, for some, the event id), and the card links the
event page; title and page come from the card (the box office's names are
terser: "Royal Northern Sinfonia" for the site's "Vivaldi's Four Seasons,
with Maria Włoszczowska & Royal Northern Sinfonia"). No show pages need
fetching.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "kings-place"
CLIENT = spk.Client("kingsplace", "https://ticketing.purchase.kingsplace.co.uk")
SITE = "https://www.kingsplace.co.uk"
LISTING_URL = f"{SITE}/whats-on/"
GENRES = {"classical": "classical", "folk": "folk", "jazz": "jazz"}
MAX_PAGES = 40

_EVENT_PAGE = re.compile(r"https://www\.kingsplace\.co\.uk/whats-on/([^/]+)/[^/]+/")


def parse_cards(page: str) -> list[dict]:
    """A listing page's cards: {"id": Spektrix id, "genre": URL path
    segment, "url": event page, "title": the site's title, "online":
    streamed}."""
    cards = []
    for card in BeautifulSoup(page, "html.parser").select("#grid .grid-item[data-id]"):
        url = next((a["href"] for a in card.select("a[href]") if _EVENT_PAGE.fullmatch(a["href"])), None)
        if not url:
            continue
        title = card.select_one(".grid-item__title")
        cards.append({
            "id": card["data-id"].strip(),
            "title": re.sub(r"\s+", " ", title.get_text(" ")).strip() if title else "",
            "genre": _EVENT_PAGE.fullmatch(url).group(1),
            "url": url,
            "online": "online-events" in (card.get("class") or []),
        })
    return cards


def has_next_page(page: str, number: int) -> bool:
    return f"/whats-on/page/{number + 1}/" in page


def fetch_cards() -> list[dict]:
    cards: list[dict] = []
    for number in range(1, MAX_PAGES + 1):
        url = LISTING_URL if number == 1 else f"{LISTING_URL}page/{number}/"
        page = fetch(url, headers=CARTELITA_BROWSER_HEADERS, impersonate=True)
        cards += parse_cards(page)
        if not has_next_page(page, number):
            break
    if not cards:
        raise ValueError("kingsplace.co.uk: no what's-on cards found")
    return cards


class Programme:
    """Curation and page of each Spektrix event, from the listing cards
    (joined by `prepare`, before curation)."""

    def __init__(self, cards: list[dict]):
        self.cards = cards
        self.listed: dict[str, dict] = {}

    def prepare(self, events: list[dict], instances: list[dict]) -> None:
        by_id = {c["id"]: c for c in self.cards if not c["online"]}
        event_ids = {e["id"] for e in events}
        for inst in instances:
            card = by_id.get(inst["id"])
            if card:
                self.listed.setdefault(inst["event"]["id"], card)
        for event_id in event_ids:
            if event_id in by_id:
                self.listed.setdefault(event_id, by_id[event_id])

    def categorize(self, event: dict) -> list[str]:
        card = self.listed.get(event["id"])
        return [GENRES[card["genre"]]] if card and card["genre"] in GENRES else []

    def title(self, event: dict) -> str:
        name = (self.listed.get(event["id"]) or {}).get("title") or event["name"]
        return re.sub(r"\s+", " ", name).strip()

    def url(self, event: dict) -> str | None:
        return (self.listed.get(event["id"]) or {}).get("url")


class KingsPlaceScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        programme = Programme(fetch_cards())
        return spk.scrape(CLIENT, programme.categorize, prepare=programme.prepare,
                          title=programme.title, url=programme.url)


register(
    scraper=KingsPlaceScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Kings Place",
        city_slug="london",
        address="90 York Way, London N1 9AG",
        site_url=SITE,
        instagram_url="https://www.instagram.com/kingsplace",
        category_slugs=["classical", "folk", "jazz"],
        list_memberships=[
            ListMembership(list_slug="classical", whitelist_category_slug="classical"),
            ListMembership(list_slug="folk", whitelist_category_slug="folk"),
            ListMembership(list_slug="jazz", whitelist_category_slug="jazz"),
        ],
    ),
)
