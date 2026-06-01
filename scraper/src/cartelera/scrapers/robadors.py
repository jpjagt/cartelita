from __future__ import annotations
import datetime as dt
import html as html_module
import json
import re

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# 23 Robadors (Harlem Jazz Club) homepage — the JSON-LD Event array on this
# single page covers the full agenda (~55 events).  The blob carries name,
# startDate, endDate, image, url, offers.price + offers.priceCurrency, and a
# one-line description used as a genre tag.  No separate list/llista view exists
# — the site redirects /agenda/, /events/, etc. back to the homepage.
AGENDA_URL = "https://23robadors.com/"
BASE_URL = "https://23robadors.com"
VENUE_SLUG = "robadors"

# Genre keywords that mean "flamenco" (description field is free-form).
# Everything else is treated as a jazz/live-music event.
_FLAMENCO_KEYWORDS = {"flamenco"}
# Events whose title equals one of these (case-insensitive) should be skipped —
# they are closure notices, not real events.
_SKIP_TITLES = {"tancat", "closed", "tancat / closed"}


def _strip_html(text: str) -> str:
    unescaped = html_module.unescape(text)
    return BeautifulSoup(unescaped, "html.parser").get_text(separator=" ", strip=True)


def _parse_iso(value: str) -> tuple[dt.date, dt.time | None]:
    """Parse an ISO-8601 datetime string, stripping the TZ offset."""
    value = re.sub(r"[+-]\d{2}:\d{2}$", "", value).rstrip("Z")
    if "T" in value:
        parsed = dt.datetime.fromisoformat(value)
        return parsed.date(), parsed.time()
    return dt.date.fromisoformat(value), None


def _normalize_url(url: str) -> str:
    return url.split("?")[0].rstrip("/")


def _extract_external_id(url: str) -> str | None:
    m = re.search(r"/calendari/([^/?#]+)", url)
    return m.group(1) if m else None


def _classify_description(raw_desc: str) -> tuple[str, list[str]]:
    """Return (category_slug, annotations) from the description/genre field.

    Rules:
    - The description contains a genre keyword (e.g. "FLAMENCO", "JAZZSESSION").
    - All live-music events map to the `jazz` top-level category.
    - "FLAMENCO" additionally gets `flamenco` in annotations.
    - Other genre strings (e.g. "LA JAM DE JAZZ", "JAZZSESSION") go into
      annotations verbatim (lower-cased, trimmed), unless they would duplicate
      the category name.
    """
    text = _strip_html(raw_desc).replace("\\n", "").strip()
    # Split on "/" to handle compound descriptions like "JAZZSESSION / COL·LECTIU VINT·I·TRES"
    parts = [p.strip() for p in text.split("/")]
    primary = parts[0].lower() if parts else ""

    annotations: list[str] = []
    if primary in _FLAMENCO_KEYWORDS:
        annotations.append("flamenco")
    else:
        # Keep the genre label as an annotation (normalised, drop empty)
        for p in parts:
            cleaned = p.strip()
            if cleaned and cleaned.lower() != "jazz":
                annotations.append(cleaned)

    return "jazz", annotations


def parse_agenda(html: str) -> list[ScrapedEvent]:
    """Parse the 23 Robadors homepage JSON-LD Event array into ScrapedEvents.

    Primary (and only) data source is the ``application/ld+json`` script tag
    on the homepage.  It carries every field we need — title, ISO datetimes,
    image, detail URL, price — unlike the Jamboree case where JSON-LD was
    incomplete.  The ``description`` field encodes a genre keyword which drives
    category and annotation assignment.

    Closure notices ("TANCAT / CLOSED") are skipped — they appear in the JSON-LD
    but are not real events.
    """
    soup = BeautifulSoup(html, "html.parser")

    blob: list[dict] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, list) and data and data[0].get("@type") == "Event":
            blob = data
            break

    events: list[ScrapedEvent] = []
    seen: set[str] = set()

    for item in blob:
        if item.get("@type") != "Event":
            continue

        title = _strip_html(item.get("name", "")).strip()
        if not title:
            continue
        if title.lower() in _SKIP_TITLES:
            continue

        source_url = _normalize_url(item.get("url", ""))
        if not source_url:
            continue
        if source_url in seen:
            continue
        seen.add(source_url)

        raw_start = item.get("startDate", "")
        if not raw_start:
            continue
        try:
            start_date, start_time = _parse_iso(raw_start)
        except (ValueError, AttributeError):
            continue

        end_date = end_time = None
        raw_end = item.get("endDate", "")
        if raw_end:
            try:
                end_date, end_time = _parse_iso(raw_end)
            except (ValueError, AttributeError):
                pass

        # When startDate == endDate exactly (common on this site) the endDate
        # carries no additional information — drop it.
        if end_date == start_date and end_time == start_time:
            end_date = end_time = None

        offers = item.get("offers", {})
        price: str | None = None
        raw_price = str(offers.get("price", "")).strip()
        currency = str(offers.get("priceCurrency", "")).strip()
        if raw_price and raw_price != "0":
            price = f"{raw_price}€" if currency == "EUR" else raw_price
        elif raw_price == "0":
            price = "free"

        image_url = item.get("image") or None

        raw_desc = item.get("description", "")
        category, annotations = _classify_description(raw_desc)

        recurrence_hint: str | None = None
        if "jam" in title.lower():
            recurrence_hint = "weekly"

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                end_date=end_date,
                end_time=end_time,
                source_url=source_url,
                category_slugs=[category],
                price=price,
                image_url=image_url,
                external_id=_extract_external_id(source_url),
                recurrence_hint=recurrence_hint,
                annotations=annotations,
            )
        )

    return events


class RobadorsScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        html = httpx.get(AGENDA_URL, follow_redirects=True, timeout=30).text
        return parse_agenda(html)


register(
    scraper=RobadorsScraper(),
    venue=VenueDefinition(
        slug="robadors",
        name="23 Robadors",
        city_slug="barcelona",
        address="Carrer d'en Robador, 23, El Raval, 08001 Barcelona",
        site_url="https://23robadors.com",
        category_slugs=["jazz"],
        list_memberships=[
            ListMembership(list_slug="jazz"),
        ],
    ),
)
