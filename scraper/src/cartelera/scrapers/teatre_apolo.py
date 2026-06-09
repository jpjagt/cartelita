from __future__ import annotations

# Teatre Apolo (Avinguda del Paral·lel 59, Barcelona) is a historic ~900-seat
# theatre with broad programming: musicals, dance, concerts, comedy, magic,
# and children's shows.
#
# Data source: the /cartelera/ listing page renders one `.elementor-post` card
# per active show, carrying: title (h2.elementor-heading-title), detail URL,
# a date-range string (.elementor-widget-text-editor), category via WordPress
# CSS classes (category-musical, category-danza, etc.), an image, and a
# category badge button (.elementor-button-text). Prices are NOT on the list
# page; they live on each show's detail page under the label "Mejor Precio".
#
# See teatre_apolo_SOURCE.md for full field mapping.

import asyncio
import datetime as dt
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

CARTELERA_URL = "https://teatreapolo.com/cartelera/"
BASE_URL = "https://teatreapolo.com"
VENUE_SLUG = "teatre-apolo"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

_MAX_CONCURRENCY = 6

# WordPress category class → our category slug(s).
# category-musical    → theater (musical theatre)
# category-danza      → dance (may be flamenco when title indicates it)
# category-concierto  → pop (tribute bands, film-music concerts, pop/rock)
# category-comedia    → theater
# category-drama-clasico → theater
# category-varios-estilos → theater (magic shows, variety; default catch-all)
# category-infantil   → kids
_WP_CAT_MAP: dict[str, str] = {
    "category-musical": "theater",
    "category-danza": "dance",
    "category-concierto": "pop",
    "category-comedia": "theater",
    "category-drama-clasico": "theater",
    "category-varios-estilos": "theater",
    "category-infantil": "kids",
}

# Flamenco keywords: if a danza show title contains any of these, add flamenco.
_FLAMENCO_KEYWORDS = re.compile(
    r"\bflamenco\b|\bflamenco\b|cía\s+flamenca|compañía\s+flamenca|baile\s+flamenco",
    re.IGNORECASE,
)

# ── Date parsing ─────────────────────────────────────────────────────────────
# Spanish month names → month numbers.
_MONTHS_ES: dict[str, int] = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_MONTH_PATTERN = "(" + "|".join(_MONTHS_ES) + ")"

# Full date: "D de Month de YYYY"
_FULL_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+de\s+" + _MONTH_PATTERN + r"\s+de\s+(\d{4})\b",
    re.IGNORECASE,
)
# Partial date: "D de Month" (no year — used when the year appears later)
_PARTIAL_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+de\s+" + _MONTH_PATTERN + r"\b",
    re.IGNORECASE,
)

# Same-month range: "Del D al D de Month de YYYY"
_SAME_MONTH_RANGE_RE = re.compile(
    r"\bDel?\s+(\d{1,2})\s+al?\s+(\d{1,2})\s+de\s+" + _MONTH_PATTERN + r"\s+de\s+(\d{4})\b",
    re.IGNORECASE,
)
# Same-month two dates: "D y D de Month de YYYY"
_SAME_MONTH_TWO_RE = re.compile(
    r"\b(\d{1,2})\s+y\s+(\d{1,2})\s+de\s+" + _MONTH_PATTERN + r"\s+de\s+(\d{4})\b",
    re.IGNORECASE,
)


def _make_date(day: str, month: str, year: str) -> dt.date:
    return dt.date(int(year), _MONTHS_ES[month.lower()], int(day))


def _parse_dates(text: str) -> tuple[dt.date, dt.date | None] | None:
    """Parse Spanish date text into (start, end | None).

    Handles the following formats (all found in the fixture):
    - "Del D al D de Month de YYYY"                      → same-month range
    - "Del D de Month de YYYY al D de Month de YYYY"     → cross-month range
    - "Del D de Month al D de Month de YYYY"             → cross-month range (year at end)
    - "D de Month de YYYY a D de Month de YYYY"          → range (alt connector)
    - "D de Month a D de Month de YYYY"                  → range (year at end)
    - "D y D de Month de YYYY"                           → two same-month dates
    - "D de Month y D de Month de YYYY"                  → two diff-month dates
    - "[Weekday] D de Month de YYYY"                     → single date
    - "D de Month de YYYY"                               → single date
    """
    # Pattern 1: Same-month range "Del D al D de Month de YYYY"
    m = _SAME_MONTH_RANGE_RE.search(text)
    if m:
        start_day, end_day, month, year = m.group(1), m.group(2), m.group(3), m.group(4)
        start = _make_date(start_day, month, year)
        end = _make_date(end_day, month, year)
        return start, (end if end != start else None)

    # Pattern 2: Same-month two dates "D y D de Month de YYYY"
    m = _SAME_MONTH_TWO_RE.search(text)
    if m:
        start_day, end_day, month, year = m.group(1), m.group(2), m.group(3), m.group(4)
        start = _make_date(start_day, month, year)
        end = _make_date(end_day, month, year)
        return start, (end if end != start else None)

    # Pattern 3: Two full dates (handles cross-month ranges and two-date texts)
    full_dates = _FULL_DATE_RE.findall(text)
    if len(full_dates) >= 2:
        start = _make_date(*full_dates[0])
        end = _make_date(*full_dates[-1])
        return start, (end if end != start else None)

    # Pattern 4: One full date + one partial date (year only at end).
    # "Del D de Month al D de Month de YYYY" or "D de Month a D de Month de YYYY"
    if len(full_dates) == 1:
        # The full date is the end; find a partial date before it as start.
        end = _make_date(*full_dates[0])
        # Find all partial dates in the text (day + month only).
        partials = _PARTIAL_DATE_RE.findall(text)
        # Filter to partials that come before the end date position.
        end_match = _FULL_DATE_RE.search(text)
        before_end = text[:end_match.start()] if end_match else text
        before_partials = _PARTIAL_DATE_RE.findall(before_end)
        if before_partials:
            # Use the last partial date before the end as the start, with end's year.
            day, month = before_partials[-1]
            start = _make_date(day, month, str(end.year))
            # Handle the case where start is in the following month of the previous year
            # (shouldn't happen for upcoming shows, but guard anyway).
            if start > end:
                start = _make_date(day, month, str(end.year - 1))
            return start, (end if end != start else None)
        return end, None

    # Pattern 5: No full date found; single partial date with no year — shouldn't
    # occur in this dataset. Return None.
    return None


# ── Price parsing ─────────────────────────────────────────────────────────────
# Detail pages show "Mejor Precio 30€" inside .elementor-widget-text-editor.
_PRICE_RE = re.compile(r"Mejor\s+Precio\s+(\d+(?:[.,]\d+)?)\s*€", re.IGNORECASE)
_FREE_RE = re.compile(
    r"entrada\s+gratuita|entrada\s+gratuï?ta|entrada\s+libre|gratis|gratuï?t",
    re.IGNORECASE,
)
_SOLD_OUT_RE = re.compile(r"\bs\.?o\.?\b|sold\s*out|exhaurit|agotad", re.IGNORECASE)


def parse_detail_price(html: str) -> str | None:
    """Extract the 'Mejor Precio XX€' from a show detail page."""
    soup = BeautifulSoup(html, "html.parser")
    for container in soup.select(".elementor-widget-text-editor .elementor-widget-container"):
        text = container.get_text(" ", strip=True)
        m = _PRICE_RE.search(text)
        if m:
            amount_str = m.group(1).replace(",", ".")
            amount = float(amount_str)
            if amount == 0:
                return "free"
            return f"{int(amount) if amount == int(amount) else amount}€"
        if _SOLD_OUT_RE.search(text):
            return "sold-out"
        if _FREE_RE.search(text):
            return "free"
    return None


# ── Category logic ────────────────────────────────────────────────────────────

def _categories_for_card(card: Tag) -> list[str]:
    """Map WordPress category CSS classes to our slugs.

    All matching non-cartelera categories are collected; unknown classes are
    ignored. For danza events with flamenco in the title, flamenco is added.
    At least one slug is always returned (defaulting to 'theater').
    """
    wp_cats = [
        cls
        for cls in card.get("class", [])
        if cls.startswith("category-") and cls != "category-cartelera"
    ]
    slugs: list[str] = []
    is_danza = False
    for wp_cat in wp_cats:
        slug = _WP_CAT_MAP.get(wp_cat)
        if slug and slug not in slugs:
            slugs.append(slug)
        if wp_cat == "category-danza":
            is_danza = True

    # Flamenco detection: check the title and button text.
    if is_danza:
        title_el = card.select_one(".elementor-heading-title")
        title_text = title_el.get_text(strip=True) if title_el else ""
        if _FLAMENCO_KEYWORDS.search(title_text):
            if "flamenco" not in slugs:
                slugs.append("flamenco")

    return slugs or ["theater"]


# ── Image extraction ──────────────────────────────────────────────────────────

def _extract_image_url(card: Tag) -> str | None:
    img = card.select_one("img")
    if not img:
        return None
    src = img.get("src", "").strip()
    return src or None


# ── External ID ───────────────────────────────────────────────────────────────

def _external_id(source_url: str) -> str:
    """Derive a per-show external ID from the URL slug.

    Each show at Teatre Apolo is one engagement (one slug = one run); there is
    no repeat-booking of the same slug. So the slug alone is a stable, unique
    per-occurrence key.
    """
    # e.g. https://teatreapolo.com/cartelera/tarzan-el-musical/ → tarzan-el-musical
    return source_url.rstrip("/").rsplit("/", 1)[-1]


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_agenda(html: str) -> list[ScrapedEvent]:
    """Parse the Teatre Apolo /cartelera/ listing into ScrapedEvents.

    One event per .elementor-post card. Date ranges are read from the first
    .elementor-widget-text-editor widget-container on the card. Category is
    derived from WordPress CSS classes. Price is NOT available on the list
    page (enriched from detail pages in scrape()). Image URL and external_id
    are extracted from the card.
    """
    soup = BeautifulSoup(html, "html.parser")
    events: list[ScrapedEvent] = []
    seen_ids: set[str] = set()

    for card in soup.select("article.elementor-post"):
        # Title
        title_el = card.select_one("h2.elementor-heading-title, h3.elementor-heading-title")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title:
            continue

        # Detail URL
        link = title_el.select_one("a") or card.select_one("h2 a, h3 a")
        if not link:
            continue
        href = link.get("href", "").strip()
        if not href:
            continue
        source_url = href if href.startswith("http") else BASE_URL + href

        # External ID
        ext_id = _external_id(source_url)
        if ext_id in seen_ids:
            continue
        seen_ids.add(ext_id)

        # Date
        text_containers = card.select(".elementor-widget-text-editor .elementor-widget-container")
        date_text: str | None = None
        for tc in text_containers:
            t = tc.get_text(strip=True)
            if t:
                date_text = t
                break
        if not date_text:
            continue
        parsed = _parse_dates(date_text)
        if not parsed:
            continue
        start_date, end_date = parsed

        # Categories
        category_slugs = _categories_for_card(card)

        # Image
        image_url = _extract_image_url(card)

        # Badge text (for annotation)
        btn = card.select_one(".elementor-button-text")
        badge = btn.get_text(strip=True) if btn else None

        annotations: list[str] = []
        if badge:
            annotations.append(badge)

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                end_date=end_date,
                source_url=source_url,
                category_slugs=category_slugs,
                price=None,  # enriched from detail page in scrape()
                image_url=image_url,
                external_id=ext_id,
                annotations=annotations,
            )
        )

    return events


# ── Price enrichment (async) ───────────────────────────────────────────────────

async def _enrich_prices(events: list[ScrapedEvent]) -> None:
    """Fetch each show's detail page to populate its ticket price (best-effort)."""
    sem = asyncio.Semaphore(_MAX_CONCURRENCY)

    async def fetch_one(event: ScrapedEvent, client: httpx.AsyncClient) -> None:
        async with sem:
            try:
                resp = await client.get(
                    event.source_url,
                    follow_redirects=True,
                    timeout=30,
                    headers=_HEADERS,
                )
                resp.raise_for_status()
            except httpx.HTTPError:
                return
        event.price = parse_detail_price(resp.text)

    async with httpx.AsyncClient() as client:
        await asyncio.gather(*(fetch_one(ev, client) for ev in events))


# ── Scraper class ─────────────────────────────────────────────────────────────

class TeatreApoloScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        html = httpx.get(
            CARTELERA_URL,
            follow_redirects=True,
            timeout=30,
            headers=_HEADERS,
        ).text
        events = parse_agenda(html)
        asyncio.run(_enrich_prices(events))
        return events


register(
    scraper=TeatreApoloScraper(),
    venue=VenueDefinition(
        slug="teatre-apolo",
        name="Teatre Apolo",
        city_slug="barcelona",
        address="Avinguda del Paral·lel, 59, 08004 Barcelona",
        site_url="https://teatreapolo.com",
        category_slugs=["theater", "dance", "pop", "kids", "flamenco"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
            ListMembership(list_slug="pop", whitelist_category_slug="pop"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
            ListMembership(list_slug="flamenco", whitelist_category_slug="flamenco"),
        ],
    ),
)
