"""Maas theater en dans — Rotterdam's youth theatre/dance company and its own
stage, the Maaspodium. Source `maas`, one venue: `maaspodium`.

See maas_SOURCE.md for the field map, curation rules and exclusions.

Data:
- `GET https://www.maastd.nl/ajax/showsearch/?culture=nl-NL&showPeriod=all
  &page=1&take=1000` — the agenda's own XHR JSON: one entry per performance
  (`Shows[]`, ~220) with ISO start (`DatumTheaterDisplay`), hall
  (`ShowZaal.IsMaaspodium`), age (`Leeftijd`), `Uitverkocht`, `Geannuleerd`,
  per-occurrence `EventId`. School-only performances are not in this feed.
- each production's page (`ShowUrl`, ~75 fetched): the spec block's `Genre:`
  (`.showheader__specs--types strong`) and price (`.showheader__prices`,
  "Vanaf € 12,50 per ticket") — neither is in the JSON.

Only performances AT the Maaspodium are kept: Maas tours the country, and its
Rotterdam dates elsewhere (Theater Rotterdam, Zuidplein) belong to those
venues' owning sources.
"""
from __future__ import annotations

import datetime as dt
import re

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register_source
from cartelera.types import (
    ListMembership,
    ScrapedEvent,
    SourceDefinition,
    VenueDefinition,
)

SOURCE_SLUG = "maas"
VENUE_SLUG = "maaspodium"
BASE_URL = "https://www.maastd.nl"
SEARCH_URL = f"{BASE_URL}/ajax/showsearch/"
SEARCH_PARAMS = {
    "culture": "nl-NL",
    "showLabels": "",
    "showPeriod": "all",
    "searchTerm": "",
    "page": 1,
    "take": 1000,
    "orderBy": "",
    "isMobile": "false",
    "isHomepage": "false",
}
USER_AGENT = "Mozilla/5.0 (compatible; Cartelita (+https://cartelita.july.dev))"

# Genre tokens on the production page ("Fysiek theater, Danstheater, Dans").
# Anything containing "dans" or "hiphop" is dance; theatre forms are theater.
# A production can be both ("Theater, Dans").
_DANCE_RE = re.compile(r"dans|hiphop", re.I)
_THEATER_RE = re.compile(r"theater|toneel|comedy|mime|opera", re.I)
# Non-performance genres: the weekly ballroom practice night is "Dans, Workshop".
_EXCLUDED_RE = re.compile(r"workshop|cursus|les\b", re.I)
_AGE_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\+")
_PRICE_RE = re.compile(r"€\s*(\d+)(?:,(\d{2}))?")


def parse_detail(html: str) -> dict | None:
    """Production page -> {genres: [...], price: str|None}. None when the
    page's spec block has neither an age (Leeftijd) nor a genre — e.g. the
    "open atelier" listing (maker only, no price), which is not a programmed
    performance."""
    soup = BeautifulSoup(html, "html.parser")
    types = soup.select_one(".showheader__specs--types strong")
    if types is None and soup.select_one(".showheader__specs--age") is None:
        return None
    genres = (
        [g.strip() for g in types.get_text(" ", strip=True).split(",") if g.strip()]
        if types else []
    )
    price = None
    prices = soup.select_one(".showheader__prices")
    if prices:
        m = _PRICE_RE.search(prices.get_text(" ", strip=True))
        if m:
            euros, cents = m.group(1), m.group(2)
            if cents and cents != "00":
                price = f"{euros},{cents}€"
            elif int(euros) == 0:
                price = "free"
            else:
                price = f"{euros}€"
    return {"genres": genres, "price": price}


def _is_kids(age: str | None) -> bool:
    """Maas's own age label: "4+", "1,5+", "Jongeren en volwassenen". The site
    splits its programme into "Families" and "Voor 12+" — under 12 is kids."""
    m = _AGE_RE.match((age or "").strip())
    return bool(m) and float(m.group(1).replace(",", ".")) < 12


def categorize(genres: list[str], age: str | None) -> list[str] | None:
    """Category slugs from the production's own Genre field, or None to skip."""
    if any(_EXCLUDED_RE.search(g) for g in genres):
        return None
    cats: list[str] = []
    if any(_THEATER_RE.search(g) and not _DANCE_RE.search(g) for g in genres):
        cats.append("theater")
    if any(_DANCE_RE.search(g) for g in genres):
        cats.append("dance")
    if not cats:
        # No/unknown genre on a performance page: Maas is a theatre company.
        cats.append("theater")
    if _is_kids(age):
        cats.append("kids")
    return cats


def _title(show: dict) -> str:
    # `TitelMetLeeftijd` is the title as printed on the site ("DAG POES /  4+");
    # collapse its double spaces.
    return " ".join((show.get("TitelMetLeeftijd") or show.get("Titel") or "").split())


def _image(show: dict) -> str | None:
    m = re.search(r'<img src="([^"?]+)', show.get("AfbeeldingHtmlString") or "")
    return BASE_URL + m.group(1) if m else None


def detail_urls(data: dict) -> list[str]:
    return sorted({
        BASE_URL + s["ShowUrl"] for s in data.get("Shows") or []
        if (s.get("ShowZaal") or {}).get("IsMaaspodium") and s.get("ShowUrl")
    })


def parse_shows(data: dict, details: dict[str, str]) -> list[ScrapedEvent]:
    """Pure: the showsearch JSON + {production url: page html} -> events at
    the Maaspodium. A production whose page wasn't fetched falls back to the
    venue's default category (theater) and no price."""
    shows = [
        s for s in data.get("Shows") or []
        if (s.get("ShowZaal") or {}).get("IsMaaspodium") and not s.get("Geannuleerd")
    ]
    parsed: dict[str, dict | None] = {}
    for url, html in details.items():
        parsed[url] = parse_detail(html)

    # The feed sometimes carries a 00:00 placeholder entry next to the real
    # timed sessions of the same production on the same day — drop those.
    timed_days = {
        (s["ShowUrl"], s["DatumTheaterDisplay"][:10]) for s in shows
        if s["DatumTheaterDisplay"][11:16] != "00:00"
    }

    events: list[ScrapedEvent] = []
    for s in shows:
        start = dt.datetime.fromisoformat(s["DatumTheaterDisplay"])
        if start.time() == dt.time(0, 0) and (s["ShowUrl"], start.date().isoformat()) in timed_days:
            continue
        url = BASE_URL + s["ShowUrl"]
        detail = parsed[url] if url in parsed else {"genres": [], "price": None}
        if detail is None:
            continue  # not a performance page
        cats = categorize(detail["genres"], s.get("Leeftijd"))
        if cats is None:
            continue
        start_time = None if start.time() == dt.time(0, 0) else start.time().replace(second=0)
        annotations = list(detail["genres"])
        if s.get("Leeftijd"):
            annotations.append(s["Leeftijd"].strip())
        events.append(
            ScrapedEvent(
                title=_title(s),
                start_date=start.date(),
                start_time=start_time,
                source_url=s.get("absoluteUrl") or url,
                category_slugs=cats,
                price="sold-out" if s.get("Uitverkocht") else detail["price"],
                description=(s.get("Subtitel") or None),
                image_url=_image(s),
                external_id=str(s["EventId"]),
                language="Language no problem" if s.get("LanguageNoProblem") else None,
                annotations=annotations,
                venue_slug=VENUE_SLUG,
            )
        )
    return events


class MaasScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True
        ) as client:
            resp = client.get(SEARCH_URL, params=SEARCH_PARAMS)
            resp.raise_for_status()
            data = resp.json()
            details: dict[str, str] = {}
            for url in detail_urls(data):
                r = client.get(url)
                if r.status_code == 200:
                    details[url] = r.text
        return parse_shows(data, details)


register_source(
    scraper=MaasScraper(),
    source=SourceDefinition(
        slug=SOURCE_SLUG,
        name="Maas theater en dans",
        venues=[
            VenueDefinition(
                slug=VENUE_SLUG,
                name="Maaspodium (Maas theater en dans)",
                city_slug="rotterdam",
                address="Sint-Jobsweg 3, 3024 EH Rotterdam",
                site_url=BASE_URL,
                category_slugs=["theater", "dance", "kids"],
                list_memberships=[
                    ListMembership(list_slug="theater", whitelist_category_slug="theater"),
                    ListMembership(list_slug="dance", whitelist_category_slug="dance"),
                    ListMembership(list_slug="kids", whitelist_category_slug="kids"),
                ],
            ),
        ],
    ),
)
