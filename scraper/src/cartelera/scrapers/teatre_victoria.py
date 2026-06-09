from __future__ import annotations

# Teatre Victòria (Av. Paral·lel 67-69, Barcelona) — a large-format theatre on
# the Paral·lel known for musicals, stand-up comedy, and big-ticket shows.
#
# Data source: JSON-LD Event entries embedded in each show's detail page
# (script[type="application/ld+json"]).  The second <script> block is a list
# of per-occurrence Event objects that carries every field we need: startDate
# (ISO-8601 with time+tz), offers.price, and offers.availability.  The agenda
# listing page is used only to discover the set of detail page URLs; it does not
# carry price or per-session dates.
#
# Category: all shows are `theater`.  The venue stages musicals, comedy monologues,
# magic shows, and similar large-format theatre productions — everything maps to
# the top-level `theater` category.
#
# external_id: the show's numeric ID (from the `id_NNN` CSS class on the listing
# card) qualified with date+time — `"{show_id}@{date}T{HHMM}"` — to ensure one
# row per occurrence.  Without the date+time qualifier, multiple sessions of the
# same show would collapse to a single row on upsert.
#
# Price: extracted directly from `offers.price` (a float, e.g. 42.0 → "42€").
# "SoldOut" availability maps to `"sold-out"`.  Price 0 → `"free"`.
#
# Source: https://www.teatrevictoria.com/ca/cartellera.html
# Last verified: 2026-06-09

import datetime as dt
import json
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.scrapers.price import format_eur_range
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

AGENDA_URL = "https://www.teatrevictoria.com/ca/cartellera.html"
BASE_URL = "https://www.teatrevictoria.com"
VENUE_SLUG = "teatre-victoria"

_SOLD_OUT_STATUS = "https://schema.org/SoldOut"
_IN_STOCK_STATUS = "https://schema.org/InStock"


def _parse_price(event: dict[str, Any]) -> str | None:
    """Convert a JSON-LD Event's offers block to our price convention."""
    offers = event.get("offers", {})
    if not offers:
        return None

    availability = offers.get("availability", "")
    if availability == _SOLD_OUT_STATUS:
        return "sold-out"

    price_raw = offers.get("price")
    if price_raw is None:
        return None

    try:
        price_float = float(price_raw)
    except (TypeError, ValueError):
        return None

    if price_float == 0:
        return "free"

    # Use integer euros; format_eur_range handles the 2× rule.
    # For a single flat price (no real lo/hi split), lo == hi.
    spec = offers.get("priceSpecification", {})
    try:
        lo = round(float(spec.get("minPrice", price_float)))
        hi = round(float(spec.get("maxPrice", price_float)))
    except (TypeError, ValueError):
        lo = hi = round(price_float)

    return format_eur_range(lo, hi)


def _parse_start_dt(start_date_str: str) -> tuple[dt.date, dt.time | None]:
    """Parse an ISO-8601 startDate string into (date, time|None)."""
    # Format: "2026-10-14T20:30:00+02:00" or bare "2026-10-14"
    m = re.match(
        r"(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?",
        start_date_str,
    )
    if not m:
        raise ValueError(f"Cannot parse startDate: {start_date_str!r}")
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    date = dt.date(year, month, day)
    if m.group(4) is not None:
        hour, minute = int(m.group(4)), int(m.group(5))
        # 00:00 is the all-day sentinel in some systems → leave as None
        if hour == 0 and minute == 0:
            time = None
        else:
            time = dt.time(hour, minute)
    else:
        time = None
    return date, time


def _image_url(raw: str | None) -> str | None:
    """Unescape HTML entities in image URLs (&amp; → &)."""
    if not raw:
        return None
    return raw.replace("&amp;", "&")


def _extract_show_id_from_classes(classes: list[str]) -> str | None:
    """Extract the show numeric ID from CSS classes like 'id_330'."""
    for cls in classes:
        m = re.match(r"^id_(\d+)$", cls)
        if m:
            return m.group(1)
    return None


def _extract_detail_urls(html: str) -> list[tuple[str, str]]:
    """Return list of (show_id, detail_url) from the agenda listing page."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in soup.find_all(attrs={"role": "listitem"}):
        classes = item.get("class", [])
        show_id = _extract_show_id_from_classes(classes)
        link = item.find("a", class_="titol")
        if not link:
            continue
        url = link.get("href", "")
        if not url or url in seen:
            continue
        # Ensure absolute URL
        if url.startswith("/"):
            url = BASE_URL + url
        seen.add(url)
        results.append((show_id or "", url))
    return results


def _parse_detail_page(html: str, show_id: str, detail_url: str) -> list[ScrapedEvent]:
    """Extract all per-occurrence ScrapedEvents from a show's detail page."""
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")

    events: list[ScrapedEvent] = []
    for script in scripts:
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        # The event list is the script that contains a list of Event objects
        if not isinstance(data, list):
            continue
        items = [item for item in data if isinstance(item, dict) and item.get("@type") == "Event"]
        if not items:
            continue

        # All items in this block share name/image/url/description
        first = items[0]
        title = first.get("name", "")
        image_raw = first.get("image")
        source_url = first.get("url") or detail_url

        for item in items:
            start_date_str = item.get("startDate", "")
            if not start_date_str:
                continue
            try:
                start_date, start_time = _parse_start_dt(start_date_str)
            except ValueError:
                continue

            price = _parse_price(item)

            # Build per-occurrence external_id: show_id + date + time
            if start_time:
                hhmm = start_time.strftime("%H%M")
            else:
                hhmm = "0000"
            external_id = f"{show_id}@{start_date.isoformat()}T{hhmm}"

            events.append(
                ScrapedEvent(
                    title=title,
                    start_date=start_date,
                    start_time=start_time,
                    source_url=source_url,
                    category_slugs=["theater"],
                    price=price,
                    image_url=_image_url(image_raw),
                    external_id=external_id,
                )
            )

        # Found the Event list — stop here (Product list is a duplicate)
        break

    return events


def parse_agenda(agenda_html: str, detail_pages: dict[str, str]) -> list[ScrapedEvent]:
    """Parse the Teatre Victòria programme.

    `agenda_html` is the listing page (to discover show URLs + IDs).
    `detail_pages` maps each detail page URL to its HTML content.
    Returns one ScrapedEvent per performance occurrence.
    """
    all_events: list[ScrapedEvent] = []
    for show_id, detail_url in _extract_detail_urls(agenda_html):
        html = detail_pages.get(detail_url, "")
        if not html:
            continue
        all_events.extend(_parse_detail_page(html, show_id, detail_url))
    return all_events


class TeatreVictoriaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        agenda_html = httpx.get(AGENDA_URL, follow_redirects=True, timeout=30).text
        detail_pages: dict[str, str] = {}
        for _show_id, detail_url in _extract_detail_urls(agenda_html):
            if detail_url not in detail_pages:
                detail_pages[detail_url] = httpx.get(
                    detail_url, follow_redirects=True, timeout=30
                ).text
        return parse_agenda(agenda_html, detail_pages)


register(
    scraper=TeatreVictoriaScraper(),
    venue=VenueDefinition(
        slug="teatre-victoria",
        name="Teatre Victòria",
        city_slug="barcelona",
        address="Av. del Paral·lel, 67-69, 08004 Barcelona",
        site_url="https://www.teatrevictoria.com",
        category_slugs=["theater"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug=None),
        ],
    ),
)
