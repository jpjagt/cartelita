from __future__ import annotations

import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers._eur import HEADERS, eur_amounts, format_eur
from cartelera.scrapers.http import fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# EKKO (Bemuurde Weerd WZ 3, Utrecht) — 40-year-old indie/alternative pop venue
# with concerts and club nights. WordPress, server-rendered. The agenda page
# (`/agenda/`, one page — `/agenda/page/2/` repeats it) lists every upcoming
# event as `a.event-line-item` with the venue's own type filter in
# `data-filter-value` ("concert", "club", "overig", "ekko40", comma-joined),
# date ("do 15 okt", "vr 15 jan 27"), title (+ support line) and — for shows
# EKKO presents elsewhere — a location label (De Kromme Haring, ACU,
# Jacobikerk). Time and price live only on the detail page (Open/Aanvang key-
# value blocks, the ticket button "Koop tickets | € 15.5"). See ekko_SOURCE.md.
BASE_URL = "https://ekko.nl"
AGENDA_URL = f"{BASE_URL}/agenda/"
VENUE_SLUG = "ekko"
VENUE_LOCATION = "EKKO"

# Venue type filter → our category. Items with neither (only "overig" — the
# pop quiz, a cabaret night — or only "ekko40", the anniversary tag) are not
# concert/club programme and are left out.
FILTER_CATEGORIES = {"concert": "pop", "club": "club"}

_MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}
_DATE = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")[a-z]*\.?(?:\s+'?(\d{2}))?\b", re.IGNORECASE
)
_TIME = re.compile(r"\b(\d{1,2})[:.](\d{2})\b")
_WEEKDAYS = ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag")
_DAY_PRICE = re.compile(
    r"\b(" + "|".join(_WEEKDAYS) + r")\b[^€]{0,12}€\s*(\d{1,4}(?:[.,]\d{1,2})?)", re.IGNORECASE
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def resolve_date(day: int, month: int, yy: str | None, today: dt.date) -> dt.date | None:
    """The list omits the year for the current year ("do 15 okt") and appends
    two digits otherwise ("vr 15 jan 27"). Without a year, take the nearest
    occurrence not more than two months in the past."""
    try:
        if yy:
            return dt.date(2000 + int(yy), month, day)
        for year in (today.year - 1, today.year, today.year + 1):
            candidate = dt.date(year, month, day)
            if candidate >= today - dt.timedelta(days=60):
                return candidate
    except ValueError:
        return None
    return None


def slug_of(url: str) -> str:
    return urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]


def parse_list(html: str, today: dt.date) -> list[dict]:
    """List rows that are EKKO's own concert/club programme: dicts with url,
    slug, title, date, categories, filters."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    for a in soup.select("a.event-line-item[href]"):
        url = a["href"]
        if "/event/" not in url:
            continue  # "Eten in EKKO" and other non-event rows
        slug = slug_of(url)
        if slug in seen:
            continue
        filters = [f.strip() for f in (a.get("data-filter-value") or "").split(",") if f.strip()]
        categories = [FILTER_CATEGORIES[f] for f in filters if f in FILTER_CATEGORIES]
        if not categories:
            continue
        # Off-site shows (presented by EKKO at another venue) carry a location
        # label next to the type button; EKKO's own shows don't.
        badges = next(
            (d for d in a.find_all("div", recursive=False) if d.find("button", recursive=False)),
            None,
        )
        location = badges.find("span", recursive=False) if badges else None
        if location is not None and _clean(location.get_text(" ")):
            continue
        date_div = next(
            (d for d in a.find_all("div", recursive=False) if "order-1" in (d.get("class") or [])),
            None,
        )
        m = _DATE.search(_clean(date_div.get_text(" "))) if date_div else None
        if not m:
            continue
        date = resolve_date(int(m.group(1)), _MONTHS[m.group(2).lower()[:3]], m.group(3), today)
        h3 = a.select_one("h3")
        if date is None or h3 is None:
            continue
        title = _clean(h3.get_text(" "))
        support = h3.find_next_sibling("span")
        if support is not None and _clean(support.get_text(" ")):
            title = f"{title} {_clean(support.get_text(' '))}"
        seen.add(slug)
        rows.append(
            {
                "url": url,
                "slug": slug,
                "title": title,
                "date": date,
                "categories": categories,
                "filters": filters,
            }
        )
    return rows


def _detail_fields(soup: BeautifulSoup) -> dict[str, str]:
    """Key/value info blocks: Datum, Open, Aanvang, Eindtijd, Locatie, …"""
    fields: dict[str, str] = {}
    for block in soup.select("div.uppercase.leading-tight"):
        children = [c for c in block.children if isinstance(c, Tag) and c.name == "div"]
        if len(children) == 2:
            key = _clean(children[0].get_text(" "))
            fields.setdefault(key, _clean(children[1].get_text(" ")))
    return fields


def _ticket(soup: BeautifulSoup) -> tuple[str, str | None, str]:
    """(button label, button amount text, note under the button). The button
    sits in an `a` (on sale) or a `span` (sold out / free entry) inside a
    column that also holds the note ("Incl. servicekosten", door price)."""
    for button in soup.find_all("button"):
        parts = [_clean(t) for t in button.stripped_strings]
        parts = [t for t in parts if t and t != "->"]
        text = " ".join(parts).lower()
        if not any(k in text for k in ("ticket", "uitverkocht", "gratis", "geannuleerd", "€")):
            continue
        amount = next((t for t in parts if "€" in t), None)
        label = " ".join(t for t in parts if t != amount)
        column = button.parent.parent if button.parent is not None else None
        note_el = column.select_one("div.mt-2") if column is not None else None
        note = _clean(note_el.get_text(" | ")) if note_el else ""
        return label, amount, note
    return "", None, ""


def parse_detail(html: str, date: dt.date) -> dict:
    """time, price, location and cancelled flag from a detail page."""
    soup = BeautifulSoup(html, "html.parser")
    fields = _detail_fields(soup)
    start_time = None
    for key in ("Aanvang", "Open"):
        m = _TIME.search(fields.get(key, ""))
        if m and int(m.group(1)) < 24:
            start_time = dt.time(int(m.group(1)), int(m.group(2)))
            break
    label, amount, note = _ticket(soup)
    low = label.lower()
    price: str | None = None
    if "uitverkocht" in low:
        price = "sold-out"
    else:
        value = eur_amounts(amount)[0] if amount and eur_amounts(amount) else None
        note_amounts = eur_amounts(note)
        day_prices = {d.lower(): v for d, v in _DAY_PRICE.findall(note)}
        weekday = _WEEKDAYS[date.weekday()]
        if value is not None and value > 0:
            price = format_eur(value)
        elif weekday in day_prices:
            # Festival day tickets ("Vrijdag €36,50 | Zaterdag €51,50 | …").
            price = format_eur(float(day_prices[weekday].replace(",", ".")))
        elif ("gratis" in low or value == 0) and note_amounts:
            # A free reservation, door price stated ("Aan de deur altijd €5,50").
            price = format_eur(max(note_amounts))
        elif "gratis" in low or value == 0:
            price = "free"
    return {
        "start_time": start_time,
        "price": price,
        "location": fields.get("Locatie"),
        "cancelled": "geannuleerd" in low or "afgelast" in low,
    }


def build_events(rows: list[dict], details: dict[str, str]) -> list[ScrapedEvent]:
    events: list[ScrapedEvent] = []
    for row in rows:
        info = parse_detail(details[row["url"]], row["date"]) if row["url"] in details else {}
        if info.get("cancelled"):
            continue
        location = info.get("location")
        if location and location.upper() != VENUE_LOCATION:
            continue  # presented by EKKO elsewhere
        events.append(
            ScrapedEvent(
                title=row["title"],
                start_date=row["date"],
                start_time=info.get("start_time"),
                source_url=row["url"],
                category_slugs=row["categories"],
                price=info.get("price"),
                external_id=row["slug"],
                annotations=[f for f in row["filters"] if f not in FILTER_CATEGORIES],
            )
        )
    return events


class EkkoScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        rows = parse_list(fetch(AGENDA_URL, headers=HEADERS), dt.date.today())
        with ThreadPoolExecutor(max_workers=6) as pool:
            pages = list(pool.map(lambda r: fetch(r["url"], headers=HEADERS), rows))
        details = {row["url"]: page for row, page in zip(rows, pages)}
        return build_events(rows, details)


register(
    scraper=EkkoScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="EKKO",
        city_slug="utrecht",
        address="Bemuurde Weerd WZ 3, 3513 BH Utrecht",
        site_url=BASE_URL,
        instagram_url="https://www.instagram.com/ekko.nl",
        category_slugs=["pop", "club"],
        list_memberships=[
            ListMembership(list_slug="pop", whitelist_category_slug="pop"),
            ListMembership(list_slug="club", whitelist_category_slug="club"),
        ],
    ),
)
