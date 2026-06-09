from __future__ import annotations

import datetime as dt
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers.price import format_eur_range
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Teatre Nacional de Catalunya (TNC), Barcelona.
# No JSON-LD, no __NEXT_DATA__ — this is a Drupal site.
# Data source: DOM cards on two seasonal list pages (current + next season).
# Price lives ONLY on each show's detail page (`.field-espectacle--preus`).
# scrape() fetches list pages + N detail pages in one httpx.Client session.
# All shows are `theater` category (TNC is a theater-only venue).
BASE_URL = "https://www.tnc.cat"
SEASON_URLS = [
    f"{BASE_URL}/ca/temporada-2025-2026",
    f"{BASE_URL}/ca/temporada-2026-2027",
]
VENUE_SLUG = "tnc"

_DDMMYYYY_SHORT = re.compile(r"(\d{2})/(\d{2})/(\d{2,4})")
# Price: "De 14 € a 28 €" or "14 €" or "Entrada gratuïta / Gratuït"
_PRICE_RANGE = re.compile(r"De\s+(\d+)\s*€\s+a\s+(\d+)\s*€", re.IGNORECASE)
_PRICE_SINGLE = re.compile(r"(\d+)\s*€")
_FREE_MARKERS = re.compile(r"gratu[ïi]t|gratu[ïi]ta|entrada\s+lliure|entrada\s+libre|preu\s+0", re.IGNORECASE)


def _parse_date(text: str) -> dt.date | None:
    """Parse DD/MM/YYYY or DD/MM/YY into a date."""
    m = _DDMMYYYY_SHORT.search(text)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


def _parse_date_range(text: str) -> tuple[dt.date, dt.date | None] | None:
    """Parse 'DD/MM/YYYY al DD/MM/YYYY' or 'DD/MM/YY al DD/MM/YY' or single date."""
    matches = _DDMMYYYY_SHORT.findall(text)
    if not matches:
        return None
    dates: list[dt.date] = []
    for d, mo, y in matches:
        yi = int(y)
        if yi < 100:
            yi += 2000
        try:
            dates.append(dt.date(yi, int(mo), int(d)))
        except ValueError:
            continue
    if not dates:
        return None
    start = dates[0]
    end = dates[-1] if len(dates) > 1 and dates[-1] != start else None
    return start, end


def _parse_price_from_detail(html: str) -> str | None:
    """Extract price from a TNC detail page."""
    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one(".field-espectacle--preus")
    if not el:
        return None
    text = el.get_text(" ", strip=True)
    # Remove the label "Preus" that leads the element
    text = re.sub(r"^Preus\s*", "", text, flags=re.IGNORECASE).strip()
    if not text:
        return None
    if _FREE_MARKERS.search(text):
        return "free"
    m = _PRICE_RANGE.search(text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return format_eur_range(lo, hi)
    m2 = _PRICE_SINGLE.search(text)
    if m2:
        return f"{int(m2.group(1))}€"
    return None


def _is_finished(article: Tag) -> bool:
    """Return True if the show's status badge indicates it has ended."""
    status_el = article.select_one(".card-status--finalitzat")
    return status_el is not None


def _parse_status(article: Tag) -> str | None:
    """Return the status badge text, normalised, or None."""
    el = article.select_one(".card-container-status")
    if not el:
        return None
    return el.get_text(strip=True) or None


def parse_agenda(html: str) -> list[dict]:
    """Parse a TNC season list page into raw event dicts (no detail page fetch).

    Each dict has keys: node_id, title, href, source_url, start_date, end_date,
    sala, status_badge, image_url.
    """
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []
    seen_ids: set[str] = set()

    for article in soup.select("article"):
        if _is_finished(article):
            continue

        node_id = article.get("data-history-node-id", "")
        if not node_id or node_id in seen_ids:
            continue
        seen_ids.add(node_id)

        link = article.select_one("h3 a, h2 a")
        if not link:
            continue
        title = link.get_text(strip=True)
        href = link.get("href", "")
        if not title or not href:
            continue
        source_url = href if href.startswith("http") else BASE_URL + href

        date_el = article.select_one(".field--name-field-date-range")
        if not date_el:
            continue
        date_text = date_el.get_text(" ", strip=True)
        parsed = _parse_date_range(date_text)
        if not parsed:
            continue
        start_date, end_date = parsed

        sala_el = article.select_one(".container-teaser--tags .field__item")
        sala = sala_el.get_text(strip=True) if sala_el else None

        status_badge = _parse_status(article)

        img = article.select_one("img")
        image_url: str | None = None
        if img:
            src = img.get("src", "")
            if src and not src.startswith("data:") and "logo" not in src.lower():
                image_url = src if src.startswith("http") else BASE_URL + src

        results.append(
            {
                "node_id": node_id,
                "title": title,
                "href": href,
                "source_url": source_url,
                "start_date": start_date,
                "end_date": end_date,
                "sala": sala,
                "status_badge": status_badge,
                "image_url": image_url,
            }
        )

    return results


def _build_event(raw: dict, price: str | None) -> ScrapedEvent:
    """Build a ScrapedEvent from a raw dict + fetched price."""
    annotations: list[str] = []
    if raw["sala"]:
        annotations.append(raw["sala"])
    # Status badge (e.g. "Exhaurit", "Últimes entrades!", "Premi Max") is
    # informative metadata, not a category — keep as annotation.
    status = raw["status_badge"]
    if status and status not in ("Exhaurit",):
        # "Exhaurit" is handled via price = "sold-out"; others are annotations.
        pass
    if status == "Exhaurit":
        price = "sold-out"

    return ScrapedEvent(
        title=raw["title"],
        start_date=raw["start_date"],
        end_date=raw["end_date"],
        source_url=raw["source_url"],
        category_slugs=["theater"],
        price=price,
        image_url=raw["image_url"],
        external_id=raw["node_id"],
        annotations=annotations,
    )


class TncScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        seen_node_ids: set[str] = set()
        raw_events: list[dict] = []

        with httpx.Client(follow_redirects=True, timeout=30) as client:
            # 1. Collect all active shows from both season list pages.
            for url in SEASON_URLS:
                html = client.get(url).text
                for raw in parse_agenda(html):
                    if raw["node_id"] not in seen_node_ids:
                        seen_node_ids.add(raw["node_id"])
                        raw_events.append(raw)

            # 2. Fetch each show's detail page to get its price.
            for raw in raw_events:
                price: str | None = None
                try:
                    detail_html = client.get(raw["source_url"]).text
                    price = _parse_price_from_detail(detail_html)
                except Exception:
                    pass
                events.append(_build_event(raw, price))

        return events


register(
    scraper=TncScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Teatre Nacional de Catalunya",
        city_slug="barcelona",
        address="Plaça de les Arts, 1, 08013 Barcelona",
        site_url="https://www.tnc.cat",
        category_slugs=["theater"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug=None),
        ],
    ),
)
