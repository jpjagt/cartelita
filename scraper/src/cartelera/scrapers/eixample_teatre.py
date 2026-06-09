"""Eixample Teatre scraper — comedy/theatre venue in Barcelona's Eixample district.

Data source: DOM scraping of https://www.eixampleteatre.cat/ca/programacio (list)
plus one detail-page fetch per show. Sessions (date, time, price) live only on the
detail pages under `<ul class="programacion">`. Shows without confirmed sessions
("Pròximament") are skipped.

See eixample_teatre_SOURCE.md for full field-by-field mapping.
"""
from __future__ import annotations

import datetime as dt
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

BASE_URL = "https://www.eixampleteatre.cat"
PROGRAMME_URL = f"{BASE_URL}/ca/programacio"
VENUE_SLUG = "eixample-teatre"

# Venue category tag (Catalan/Spanish) → Cartelera category slug.
# Tags absent here go into annotations instead.
_CAT_MAP: dict[str, str] = {
    "familiar": "kids",
    "family": "kids",
    # Everything else at this venue is theatrical.
    "comèdia": "theater",
    "comedia": "theater",
    "teatre": "theater",
    "teatro": "theater",
}

# Tags that are too granular for a top-level category — kept as annotations.
_ANNOTATION_TAGS = {"humor", "màgia", "magia", "monòlegs", "monologos", "metalisme", "metalismo"}

# Date pattern DD/MM/YYYY
_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
# Time pattern HH:MM h or HHh
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*h", re.IGNORECASE)
# Price pattern for sold-out detection
_SOLD_RE = re.compile(r"agotado|sold.?out|exhaurides", re.IGNORECASE)


def _slug_from_url(href: str) -> str:
    """Extract the show slug from a detail href like '/ca/Bonobos' → 'Bonobos'."""
    return href.rstrip("/").split("/")[-1]


def _parse_date(text: str) -> dt.date | None:
    m = _DATE_RE.search(text)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return dt.date(year, month, day)


def _parse_time(text: str) -> dt.time | None:
    m = _TIME_RE.search(text)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return None
    return dt.time(hour, minute)


def _parse_price(col_text: str | None, btn_text: str | None) -> str | None:
    if btn_text and _SOLD_RE.search(btn_text):
        return "sold-out"
    if not col_text:
        return None
    col_text = col_text.strip()
    if not col_text:
        return None
    # Price is already concise like "20€" or "23€" — pass through.
    # Strip surrounding whitespace.
    return col_text


def _map_categories(
    tags: list[str],
) -> tuple[list[str], list[str]]:
    """Return (category_slugs, annotation_strings) from venue tags."""
    slugs: list[str] = []
    annotations: list[str] = []
    for tag in tags:
        lower = tag.lower().strip()
        if lower in _CAT_MAP:
            slug = _CAT_MAP[lower]
            if slug not in slugs:
                slugs.append(slug)
        elif lower in _ANNOTATION_TAGS:
            annotations.append(tag)
        # otherwise ignore (e.g. venue-specific tags with no mapping)
    # Fallback: every show at this venue is at minimum a theatre show.
    if not slugs:
        slugs = ["theater"]
    return slugs, annotations


def parse_detail(html: str, source_url: str) -> list[ScrapedEvent]:
    """Parse one Eixample Teatre detail page into 0-or-more ScrapedEvents.

    Each `<li>` in `<ul class="programacion">` is one session (one occurrence).
    Returns an empty list if the show has no confirmed sessions yet.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Title
    h1 = soup.select_one("#main-ctn h1")
    title = h1.get_text(" ", strip=True) if h1 else ""
    # Strip badge text ("Novetat", "Funció especial") from title if present
    for badge in h1.select(".badge") if h1 else []:
        badge_text = badge.get_text(strip=True)
        title = title.replace(badge_text, "").strip()
    if not title:
        return []

    # Categories from detail sidebar tags
    cat_tags = [
        a.get_text(strip=True)
        for a in soup.select('.fondo-auxiliares a[href*="id_estilo"]')
    ]
    category_slugs, annotations = _map_categories(cat_tags)

    # Main image (first .img-fluid in #main-ctn)
    img_el = soup.select_one("#main-ctn img.img-fluid")
    image_url: str | None = None
    if img_el:
        src = img_el.get("src", "")
        image_url = (BASE_URL + src) if src.startswith("/") else (src or None)

    # Slug for external_id
    slug = _slug_from_url(source_url)

    events: list[ScrapedEvent] = []
    for item in soup.select("ul.programacion li"):
        # The inner row `.col-lg-8 .row` has exactly 5 direct-child divs:
        # 0=weekday, 1=date, 2=time, 3=price, 4=club-price
        inner_row = item.select_one(".col-lg-8 .row")
        if not inner_row:
            continue
        cols = inner_row.find_all("div", recursive=False)
        # Expect at least 3 cols: weekday, date, time
        if len(cols) < 3:
            continue

        # col 0 → weekday, col 1 → date, col 2 → time, col 3 → price (may be absent)
        date_text = cols[1].get_text(strip=True)
        time_text = cols[2].get_text(strip=True)
        price_text = cols[3].get_text(strip=True) if len(cols) > 3 else None
        btn = item.select_one(".btn")
        btn_text = btn.get_text(strip=True) if btn else None

        start_date = _parse_date(date_text)
        if not start_date:
            continue
        start_time = _parse_time(time_text)
        price = _parse_price(price_text, btn_text)

        # Per-occurrence external_id: slug@YYYYMMDDTHHmm
        time_part = start_time.strftime("%H%M") if start_time else "0000"
        external_id = f"{slug}@{start_date.strftime('%Y%m%d')}T{time_part}"

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=source_url,
                category_slugs=category_slugs,
                price=price,
                image_url=image_url,
                external_id=external_id,
                annotations=annotations,
            )
        )

    return events


def parse_agenda(html: str) -> list[dict]:
    """Parse the Eixample Teatre programme list page.

    Returns a list of dicts with 'href', 'image_url' for each show card.
    Dates are not on this page — only on detail pages.
    Excludes the gift-card entry ("Regala EIXAMPLE TEATRE").
    """
    soup = BeautifulSoup(html, "html.parser")
    shows: list[dict] = []
    seen_hrefs: set[str] = set()

    for card in soup.select(".col-md-3.col-sm-6"):
        link = card.select_one("h2 a")
        if not link:
            continue
        href = link.get("href", "")
        title = link.get_text(strip=True)

        # Skip the gift card page
        if "regala" in href.lower():
            continue
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        img = card.select_one("img")
        img_url: str | None = None
        if img:
            src = img.get("src", "")
            img_url = (BASE_URL + src) if src.startswith("/") else (src or None)

        shows.append({"href": href, "title": title, "image_url": img_url})

    return shows


class EixampleTeatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        agenda_html = httpx.get(
            PROGRAMME_URL, follow_redirects=True, timeout=30
        ).text
        shows = parse_agenda(agenda_html)

        events: list[ScrapedEvent] = []
        seen_ids: set[str] = set()

        for show in shows:
            detail_url = BASE_URL + show["href"]
            try:
                detail_html = httpx.get(
                    detail_url, follow_redirects=True, timeout=30
                ).text
            except httpx.HTTPError:
                continue

            for ev in parse_detail(detail_html, detail_url):
                if ev.external_id and ev.external_id in seen_ids:
                    continue
                if ev.external_id:
                    seen_ids.add(ev.external_id)
                events.append(ev)

        return events


register(
    scraper=EixampleTeatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Eixample Teatre",
        city_slug="barcelona",
        address="C/ del Consell de Cent, 425, 08009 Barcelona",
        site_url=BASE_URL,
        category_slugs=["theater", "kids"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
