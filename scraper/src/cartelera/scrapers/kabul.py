from __future__ import annotations

import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.scrapers._eur import HEADERS
from cartelera.scrapers.http import fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# KABUL à GoGo (Gietijzerstraat 3, Utrecht-Werkspoorkwartier) — club and
# cultural venue with five spaces (ABU, Teatro, Zohal, Layla, Café Oké). A
# Webflow site: the homepage server-renders the full agenda as a CMS collection
# (`.agenda-collection_wrapper`) with title, date, ROOM labels (`.area_tags`)
# and GENRE labels (`.genre_tags`, hidden when empty). Times are typed in each
# event page's rich text ("Vrijdag 16 oktober 2026 22:00–04:00"); there is no
# price on the site (tickets on weticket.io, not server-rendered), except the
# venue's own "Free Entry" label. See kabul_SOURCE.md.
BASE_URL = "https://www.kabulagogo.nl"
VENUE_SLUG = "kabul-a-gogo"

# The venue's own rooms. An event whose room labels name none of these is
# KABUL programming hosted elsewhere (e.g. "Centraal Museum") — not at this
# venue, left out.
ROOMS = {"abu", "teatro", "zohal", "layla", "café oké", "cafe oke", "terras"}

# Genre labels marking non-programme items: "Workshop" (e.g. a line-dance
# class) and "hits" — the label the venue gives only its touring sing-along
# music-bingo nights (Muziekbingo XXL, a third-party format).
EXCLUDE_LABELS = {"workshop", "hits"}
FREE_LABELS = {"free entry"}
# Genre labels for live/performance programme → alternative; every other
# genre label (house, techno, electro, breaks, dub, "Club Night", …) → club.
ALTERNATIVE_LABELS = {"live music", "performance", "poetry", "triphop", "experimental"}

_MONTHS = {
    m: i for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"], start=1)
}
_DATE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})\b", re.IGNORECASE)
_TIME_RANGE = re.compile(r"\b(\d{1,2})[:.](\d{2})\s*[–—-]\s*\d{1,2}[:.]\d{2}\b")
_FROM_PM = re.compile(r"\bfrom\s+(\d{1,2})\s*(am|pm)\b", re.IGNORECASE)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ").replace("‍", "")).strip()


def categorize(genres: list[str]) -> list[str]:
    labels = {g.lower() for g in genres} - FREE_LABELS
    cats: list[str] = []
    if labels - ALTERNATIVE_LABELS or not labels:
        cats.append("club")
    if labels & ALTERNATIVE_LABELS:
        cats.append("alternative")
    return cats


def parse_agenda(html: str) -> list[dict]:
    """Agenda rows at the venue that are programme: url, slug, title, date,
    rooms, genres, categories, free."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    for item in soup.select(".agenda-collection_wrapper"):
        a = item.select_one('a[href^="/events/"]')
        h4 = item.select_one("h4")
        if a is None or h4 is None:
            continue
        url = urljoin(BASE_URL, a["href"])
        slug = a["href"].rstrip("/").rsplit("/", 1)[-1]
        if slug in seen:
            continue
        rooms = [_clean(x.get_text(" ")) for x in item.select(".area_tags .label_regular")]
        genres = [
            _clean(x.get_text(" "))
            for x in item.select(".genre_tags:not(.w-condition-invisible) .label_regular")
        ]
        if rooms and not {r.lower() for r in rooms} & ROOMS:
            continue  # hosted off-site
        if {g.lower() for g in genres} & EXCLUDE_LABELS:
            continue
        date_text = " ".join(
            _clean(x.get_text(" "))
            for x in item.select(".div-block-23 .heading-style-h2:not(.w-condition-invisible)")
        )
        m = _DATE.search(date_text)
        if not m:
            continue
        try:
            date = dt.date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
        except ValueError:
            continue
        seen.add(slug)
        rows.append(
            {
                "url": url,
                "slug": slug,
                "title": _clean(h4.get_text(" ")),
                "date": date,
                "rooms": rooms,
                "genres": [g for g in genres if g.lower() not in FREE_LABELS],
                "categories": categorize(genres),
                "free": bool({g.lower() for g in genres} & FREE_LABELS),
            }
        )
    return rows


def detail_time(html: str) -> dt.time | None:
    """Start time from the event page's rich text: the first "22:00–04:00"
    range, else an English "From 4PM"."""
    soup = BeautifulSoup(html, "html.parser")
    for selector in (".richtext-regular", ".text-size-regular"):
        el = soup.select_one(selector)
        text = _clean(el.get_text(" ")) if el else ""
        m = _TIME_RANGE.search(text)
        if m and int(m.group(1)) < 24:
            return dt.time(int(m.group(1)), int(m.group(2)))
        m = _FROM_PM.search(text)
        if m:
            hour = int(m.group(1)) % 12 + (12 if m.group(2).lower() == "pm" else 0)
            return dt.time(hour, 0)
    return None


def build_events(rows: list[dict], details: dict[str, str]) -> list[ScrapedEvent]:
    return [
        ScrapedEvent(
            title=row["title"],
            start_date=row["date"],
            start_time=detail_time(details[row["url"]]) if row["url"] in details else None,
            source_url=row["url"],
            category_slugs=row["categories"],
            price="free" if row["free"] else None,
            external_id=row["slug"],
            annotations=row["genres"] + row["rooms"],
        )
        for row in rows
    ]


class KabulScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        rows = parse_agenda(fetch(BASE_URL + "/", headers=HEADERS))
        details = {row["url"]: fetch(row["url"], headers=HEADERS) for row in rows}
        return build_events(rows, details)


register(
    scraper=KabulScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="KABUL à GoGo",
        city_slug="utrecht",
        address="Gietijzerstraat 3, Utrecht",
        site_url=BASE_URL,
        instagram_url="https://www.instagram.com/kabulagogo",
        category_slugs=["club", "alternative"],
        list_memberships=[
            ListMembership(list_slug="club", whitelist_category_slug="club"),
            ListMembership(list_slug="alternative", whitelist_category_slug="alternative"),
        ],
    ),
)
