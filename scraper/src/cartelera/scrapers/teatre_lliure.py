"""Teatre Lliure (Barcelona) scraper.

Data source: DOM — the season list page at `/ca/temporada-25-26` renders a
`<ul id="ShowList">` with one `<li>` per show. Each card carries title, date
range, venue room, description, detail link, and thumbnail. Price and schedule
are only available on the per-show detail page (inside `.item-set` blocks with
an `<h3>` label).

Strategy
--------
1. Fetch the season list page, parse all show cards.
2. For each show, fetch the detail page to extract:
   - `Preu` (.item-set h3 == "Preu") → price string
   - `Horari` (.item-set h3 == "Horari") → schedule text kept as annotation
   - `Edat recomanada` → kept as annotation; also used as `kids` signal

Category mapping
----------------
Teatre Lliure is a performing-arts venue — every event maps to `theater`.
Exception: shows whose URL slug ends with `-elpetit`, or whose detail page
carries an `Edat recomanada` labelled for young children, are tagged `kids`.
(The `el Petit` festival itself and its sub-shows are explicitly `kids`.)

External ID
-----------
Each list-page entry is a unique show run (one item per production, not per
night). The URL slug is stable and unique, so it is used as `external_id`
without date qualification.

Date parsing
------------
The period field uses several formats:
  - `DD/MM/YY` or `DD/MM/YYYY` (single)
  - `DD/MM — DD/MM/YY` (range, em-dash, first date missing year)
  - `D, D, D i D/MM/YY` (multi-date list, year on last token only)
  - `DD/MM - DD/MM/YY` (range, hyphen)
  - `DD/MM` (no year — skipped; no canonical date available)

The parser extracts the last full DD/MM/YY(YY) token as the end date, then
infers the start from the first day-number(s) before it.

Price format
------------
"De X a Y €" → `format_eur_range(X, Y)` (range only when Y ≥ 2×X).
"Gratuït" / "Entrada gratuïta" → `"free"`.
Single "N €" → `"N€"`.

Verified: 2026-06-09
"""
from __future__ import annotations

import datetime as dt
import re
import time

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers.price import format_eur_range
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

BASE_URL = "https://www.teatrelliure.com"
SEASON_URL = f"{BASE_URL}/ca/temporada-25-26"
VENUE_SLUG = "teatre-lliure"

# Matches DD/MM/YYYY or DD/MM/YY (the full date token)
_FULL_DATE = re.compile(r"(\d{1,2})/(\d{2})/(\d{2,4})")
# Matches DD/MM not followed by /digit (partial, no year)
_PARTIAL_DATE = re.compile(r"(\d{1,2})/(\d{2})(?!/\d)")
# Any 1-2 digit day number
_DAY = re.compile(r"\b(\d{1,2})\b")

_PRICE_RANGE = re.compile(r"De\s+(\d+)\s+a\s+(\d+)\s*€", re.IGNORECASE)
_PRICE_SINGLE = re.compile(r"(\d+)\s*€")
_FREE_RE = re.compile(r"gratu[ïi]t", re.IGNORECASE)

# URL slugs that identify kids events (elpetit festival)
_KIDS_SLUG_RE = re.compile(r"elpetit", re.IGNORECASE)

# Age recommendation strings that signal a children's event
_KIDS_AGE_RE = re.compile(r"\bde\s+\d+\s+a\s+\d+\s+anys\b", re.IGNORECASE)


def _normalize_year(y: int) -> int:
    return 2000 + y if y < 100 else y


def parse_period(text: str) -> tuple[dt.date | None, dt.date | None]:
    """Parse a period string into (start_date, end_date).

    Returns (None, None) when no year can be determined (e.g. bare "DD/MM").
    Returns (start, None) for a single date.
    Returns (start, end) for a range.
    """
    full_dates = [
        (int(d), int(m), _normalize_year(int(y)))
        for d, m, y in _FULL_DATE.findall(text)
    ]

    if not full_dates:
        return None, None

    # Last full date is the canonical end date
    end_day, end_mon, end_yr = full_dates[-1]
    end_date = dt.date(end_yr, end_mon, end_day)

    if len(full_dates) >= 2:
        # Multiple full dates: first is start
        s_day, s_mon, s_yr = full_dates[0]
        start_date = dt.date(s_yr, s_mon, s_day)
        return start_date, (end_date if end_date != start_date else None)

    # Only one full date — look for a partial date (DD/MM) before it
    full_match = _FULL_DATE.search(text)
    assert full_match is not None
    full_start_pos = full_match.start()
    text_before = text[:full_start_pos]

    partials = [(int(d), int(m)) for d, m in _PARTIAL_DATE.findall(text_before)]
    if partials:
        p_day, p_mon = partials[0]
        # If the partial month is after the end month, it's from the previous year
        p_yr = end_yr - 1 if p_mon > end_mon else end_yr
        start_date = dt.date(p_yr, p_mon, p_day)
        return start_date, (end_date if end_date != start_date else None)

    # Multi-date like "05, 08, 09, 14, 15 i 16/11/25" or "21 i 22/11/25"
    day_nums = [int(d) for d in _DAY.findall(text_before) if 1 <= int(d) <= 31]
    if day_nums:
        first_day = day_nums[0]
        try:
            start_date = dt.date(end_yr, end_mon, first_day)
        except ValueError:
            return end_date, None
        return start_date, (end_date if end_date != start_date else None)

    # Single date
    return end_date, None


def parse_price(raw: str | None) -> str | None:
    """Normalise a Teatre Lliure price string to the Cartelera convention."""
    if not raw:
        return None
    m = _PRICE_RANGE.search(raw)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return format_eur_range(lo, hi)
    if _FREE_RE.search(raw):
        return "free"
    m = _PRICE_SINGLE.search(raw)
    if m:
        return f"{m.group(1)}€"
    return None


def _item_set_value(soup: BeautifulSoup | Tag, label: str) -> str | None:
    """Return the text of a `.item-set` block whose `<h3>` matches `label`."""
    for block in soup.select(".item-set"):
        h3 = block.select_one("h3")
        if h3 and h3.get_text(strip=True).lower() == label.lower():
            p = block.select_one("p, .text")
            if p:
                return p.get_text(" ", strip=True) or None
    return None


def _slug_from_href(href: str) -> str:
    """Extract the path segment (slug) from a /ca/<slug> href."""
    return href.rstrip("/").split("/")[-1]


def _image_url(li: Tag) -> str | None:
    img = li.select_one("figure img")
    if not img:
        return None
    src = img.get("src", "")
    if src.startswith("//"):
        src = "https:" + src
    return src or None


def parse_agenda(html: str) -> list[dict]:
    """Parse the season list page into a list of show dicts.

    Each dict has: title, href, slug, period_text, room, image_url, desc.
    Price is NOT available on the list page — `scrape()` fetches detail pages.
    """
    soup = BeautifulSoup(html, "html.parser")
    shows = []
    for li in soup.select("ul#ShowList > li"):
        h3 = li.select_one("h3.tit a")
        if not h3:
            continue
        title = h3.get_text(strip=True)
        href = h3.get("href", "")
        if not title or not href:
            continue

        dds = li.select("dd.outcome")
        period_text = dds[0].get_text(strip=True) if dds else ""
        room = dds[1].get_text(strip=True) if len(dds) > 1 else ""

        desc_el = li.select_one("p.desc")
        desc = desc_el.get_text(" ", strip=True) if desc_el else None

        shows.append(
            {
                "title": title,
                "href": href,
                "slug": _slug_from_href(href),
                "period_text": period_text,
                "room": room,
                "image_url": _image_url(li),
                "desc": desc,
            }
        )
    return shows


def _build_event(show: dict, detail_soup: BeautifulSoup) -> ScrapedEvent | None:
    """Combine a list-page show dict with a parsed detail page into a ScrapedEvent."""
    period_text = show["period_text"]
    start_date, end_date = parse_period(period_text)
    if start_date is None:
        return None  # Can't determine dates

    source_url = BASE_URL + show["href"]

    # Price from detail page
    raw_price = _item_set_value(detail_soup, "Preu")
    price = parse_price(raw_price)

    # Horari (schedule) → annotation
    horari = _item_set_value(detail_soup, "Horari")
    # Edat recomanada → annotation + kids signal
    edat = _item_set_value(detail_soup, "Edat recomanada")

    # Category determination
    slug = show["slug"]
    is_kids = bool(_KIDS_SLUG_RE.search(slug))
    if not is_kids and edat:
        # "De 3 a 5 anys" style → kids
        is_kids = bool(_KIDS_AGE_RE.search(edat))
    category = "kids" if is_kids else "theater"

    # Annotations: room, schedule, age recommendation
    annotations: list[str] = []
    if show["room"]:
        annotations.append(show["room"])
    if horari:
        annotations.append(horari)
    if edat:
        annotations.append(edat)

    return ScrapedEvent(
        title=show["title"],
        start_date=start_date,
        end_date=end_date,
        source_url=source_url,
        category_slugs=[category],
        price=price,
        image_url=show["image_url"],
        external_id=slug,
        annotations=annotations,
        description=show["desc"],
    )


class TeatreLliureScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        headers = {"Accept-Language": "ca"}
        season_html = httpx.get(
            SEASON_URL, follow_redirects=True, timeout=30, headers=headers
        ).text
        shows = parse_agenda(season_html)

        events: list[ScrapedEvent] = []
        for show in shows:
            detail_url = BASE_URL + show["href"]
            try:
                detail_html = httpx.get(
                    detail_url, follow_redirects=True, timeout=30, headers=headers
                ).text
                detail_soup = BeautifulSoup(detail_html, "html.parser")
                ev = _build_event(show, detail_soup)
                if ev is not None:
                    events.append(ev)
            except httpx.HTTPError:
                # Skip shows whose detail page is unreachable
                continue
            # Be polite to the server
            time.sleep(0.2)

        return events


register(
    scraper=TeatreLliureScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Teatre Lliure",
        city_slug="barcelona",
        address="Pg. de Santa Madrona, 40-46, 08038 Barcelona",
        site_url=BASE_URL,
        category_slugs=["theater", "kids"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
