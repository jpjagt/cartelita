from __future__ import annotations
import datetime as dt
import json
import re

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.scrapers.price import format_eur_range
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Teatre Poliorama (Las Ramblas / Raval, Barcelona) is a main-stage commercial
# theatre. The programme page (/ca/programacio.html) renders `.contenidor-product`
# cards, one per *show* (not per occurrence). Each card links to a detail page
# that embeds per-occurrence JSON-LD `Event` objects, one per session, with
# startDate, price, and availability. We use the detail-page JSON-LD as the
# primary source for dates, times, and prices.
#
# Category mapping (agenda card `.categoria` label → category_slug):
#   "Flamenco"            → flamenco
#   "Petit Poliorama"     → kids          (family / children's shows)
#   "Nits del Polio"      → theater       (late-night comedy/theatre)
#   "TEMPORADA 20xx/yy"   → theater       (season label — default for this venue)
#   anything else         → theater       (catch-all)
#
# external_id: venue-show-id (from URL slug) + "@" + ISO date + "T" + HHMM so
# each session is a separate row (avoids the Filmoteca collapsing trap).
AGENDA_URL = "https://www.teatrepoliorama.com/ca/programacio.html"
BASE_URL = "https://www.teatrepoliorama.com"
VENUE_SLUG = "teatre-poliorama"

# Availability schema URLs
_INSTOCK = "https://schema.org/InStock"
_SOLDOUT_AVAIL = "https://schema.org/SoldOut"
_SOLDOUT_AVAIL2 = "https://schema.org/OutOfStock"

_CATEGORY_MAP: dict[str, str] = {
    "flamenco": "flamenco",
    "petit poliorama": "kids",
    "nits del polio": "theater",
}


def _map_category(label: str) -> str:
    """Map venue category label to a cartelera category slug."""
    key = label.strip().lower()
    if key in _CATEGORY_MAP:
        return _CATEGORY_MAP[key]
    # "temporada 2025/26", "temporada 2026/27" → theater
    if key.startswith("temporada"):
        return "theater"
    return "theater"


def _parse_iso(dt_str: str) -> tuple[dt.date, dt.time | None]:
    """Parse an ISO-8601 datetime string (with or without TZ offset)."""
    # Strip TZ offset: +02:00, +01:00, Z
    clean = re.sub(r"[+Z][0-9:]+$", "", dt_str).replace("Z", "")
    if "T" in clean:
        date_part, time_part = clean.split("T", 1)
        d = dt.date.fromisoformat(date_part)
        time_part = time_part[:8]  # HH:MM:SS
        hms = time_part.split(":")
        h, m = int(hms[0]), int(hms[1]) if len(hms) > 1 else 0
        if h == 0 and m == 0:
            # midnight sentinel means time unknown
            return d, None
        return d, dt.time(h, m)
    return dt.date.fromisoformat(clean), None


def _format_price(price_val, avail: str | None) -> str | None:
    """Convert a JSON-LD price value and availability URL to a price string."""
    if avail and avail in (_SOLDOUT_AVAIL, _SOLDOUT_AVAIL2):
        return "sold-out"
    if price_val is None:
        return None
    try:
        cents = round(float(price_val) * 100)
    except (ValueError, TypeError):
        return None
    if cents == 0:
        return "free"
    euros = cents / 100
    # Format: use integer if no fractional part, else one decimal
    if cents % 100 == 0:
        return f"{int(euros)}€"
    # e.g. 15.5 → "15.5€"
    return f"{euros:g}€"


def _show_slug_from_url(url: str) -> str:
    """Extract the show slug from a detail URL like /ca/programacio/c/875-show-name.html"""
    m = re.search(r"/c/([^/?#]+?)(?:\.html)?$", url)
    return m.group(1) if m else url.split("/")[-1].replace(".html", "")


def parse_detail(html: str, detail_url: str, category_slugs: list[str]) -> list[ScrapedEvent]:
    """Parse a Teatre Poliorama show detail page into per-occurrence ScrapedEvents.

    Each `Event` JSON-LD block represents one session with its own date/time/price.
    The image and description come from the first block or the OG meta tag."""
    soup = BeautifulSoup(html, "html.parser")
    show_slug = _show_slug_from_url(detail_url)

    # Collect all Event JSON-LD blocks
    ld_events: list[dict] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, AttributeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type") == "Event":
                ld_events.append(item)

    if not ld_events:
        return []

    # Shared metadata from the first event block
    first = ld_events[0]
    title = first.get("name", "").strip()
    image_url = first.get("image") or None
    if image_url:
        # Strip HTML entities from image URL
        image_url = image_url.replace("&amp;", "&")

    # Description: strip HTML tags from description field
    raw_desc = first.get("description") or ""
    if raw_desc:
        desc_soup = BeautifulSoup(raw_desc, "html.parser")
        description: str | None = desc_soup.get_text(" ", strip=True) or None
    else:
        description = None

    events: list[ScrapedEvent] = []
    for ld in ld_events:
        start_str = ld.get("startDate")
        if not start_str:
            continue
        try:
            start_date, start_time = _parse_iso(start_str)
        except (ValueError, TypeError):
            continue

        offers = ld.get("offers") or {}
        avail = offers.get("availability")
        price_val = offers.get("price")
        price = _format_price(price_val, avail)

        # external_id: show-slug + date + time (per-occurrence key)
        time_tag = start_time.strftime("%H%M") if start_time else "0000"
        external_id = f"{show_slug}@{start_date.isoformat()}T{time_tag}"

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=detail_url,
                category_slugs=category_slugs,
                price=price,
                image_url=image_url,
                description=description,
                external_id=external_id,
            )
        )

    return events


def parse_agenda(html: str) -> list[tuple[str, list[str]]]:
    """Parse the Teatre Poliorama agenda page.

    Returns a list of (detail_url, category_slugs) tuples — one per show.
    The caller must fetch each detail URL and call parse_detail() to get events."""
    soup = BeautifulSoup(html, "html.parser")
    shows: list[tuple[str, list[str]]] = []
    seen: set[str] = set()

    for card in soup.select(".contenidor-product"):
        link = card.select_one("a.imatge")
        if not link:
            continue
        href = link.get("href", "").strip()
        if not href or href in seen:
            continue
        seen.add(href)

        # Resolve relative URLs
        if href.startswith("/"):
            href = BASE_URL + href

        # Category labels on the card
        cat_labels = [c.get_text(strip=True) for c in card.select(".categoria")]
        # Map to slugs, deduplicate
        slugs: list[str] = []
        seen_slugs: set[str] = set()
        for label in cat_labels:
            s = _map_category(label)
            if s not in seen_slugs:
                slugs.append(s)
                seen_slugs.add(s)
        if not slugs:
            slugs = ["theater"]

        shows.append((href, slugs))

    return shows


class TeatrePolioramaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        # 1. Fetch agenda page to get all show URLs
        agenda_html = httpx.get(AGENDA_URL, follow_redirects=True, timeout=30).text
        shows = parse_agenda(agenda_html)

        all_events: list[ScrapedEvent] = []
        for detail_url, category_slugs in shows:
            try:
                detail_html = httpx.get(detail_url, follow_redirects=True, timeout=30).text
            except httpx.HTTPError:
                continue
            events = parse_detail(detail_html, detail_url, category_slugs)
            all_events.extend(events)

        return all_events


register(
    scraper=TeatrePolioramaScraper(),
    venue=VenueDefinition(
        slug="teatre-poliorama",
        name="Teatre Poliorama",
        city_slug="barcelona",
        address="La Rambla, 115, 08002 Barcelona",
        site_url="https://www.teatrepoliorama.com",
        category_slugs=["theater", "flamenco", "kids"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="flamenco", whitelist_category_slug="flamenco"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
