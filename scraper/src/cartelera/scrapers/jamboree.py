from __future__ import annotations
import datetime as dt
import html as html_module
import json
import re

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent

AGENDA_URL = "https://jamboreejazz.com/agenda/"
VENUE_SLUG = "jamboree"


def _strip_html_entities(text: str) -> str:
    """Unescape HTML entities and strip remaining tags."""
    unescaped = html_module.unescape(text)
    return BeautifulSoup(unescaped, "html.parser").get_text(separator=" ", strip=True)


# The site emits local (Barcelona) wall-clock time; we keep the naive local time and drop the offset. If the source ever switches to UTC, this assumption breaks.
def _parse_iso(value: str) -> tuple[dt.date, dt.time | None]:
    """Parse ISO-8601 datetime string (with or without time part).

    Returns (date, time | None).
    """
    # Remove timezone suffix so fromisoformat works on Python <3.11
    value = re.sub(r"[+-]\d{2}:\d{2}$", "", value).rstrip("Z")
    if "T" in value:
        parsed = dt.datetime.fromisoformat(value)
        return parsed.date(), parsed.time()
    return dt.date.fromisoformat(value), None


# Returns the first price found. Multi-tier descriptions (e.g. "10€ / 15€") keep
# only the first tier — acceptable for MVP.
def _extract_price(description: str) -> str | None:
    """Try to pull a price expression from plain-text description."""
    m = re.search(r"(\d+\s*€|\€\s*\d+)", description)
    return m.group(0).replace(" ", "") if m else None


def _extract_external_id(url: str) -> str | None:
    """Extract the slug from a /esdeveniment/<slug>/ URL as the external id."""
    m = re.search(r"/esdeveniment/([^/]+)/?$", url)
    return m.group(1) if m else None


def parse_agenda(html: str) -> list[ScrapedEvent]:
    """Parse the Jamboree agenda page and return a list of ScrapedEvents.

    Uses the JSON-LD ``application/ld+json`` block that the WordPress/The Events
    Calendar plugin embeds — one ``Event`` object per listing.  This is far more
    reliable than CSS selectors because the structured data is well-formed and
    machine-readable.
    """
    soup = BeautifulSoup(html, "html.parser")

    # The page contains two JSON-LD blobs:
    #   [0] – site-level metadata (@graph with Person/WebSite/CollectionPage)
    #   [1] – flat list of Event objects, one per agenda entry
    ld_scripts = soup.find_all("script", type="application/ld+json")
    event_data: list[dict] = []
    for script in ld_scripts:
        try:
            blob = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(blob, list) and blob and blob[0].get("@type") == "Event":
            event_data = blob
            break

    if not event_data:
        return []

    events: list[ScrapedEvent] = []
    for item in event_data:
        if item.get("@type") != "Event":
            continue

        # Skip cancelled events
        status = item.get("eventStatus", "")
        if "EventCancelled" in status or "EventPostponed" in status:
            continue

        title = html_module.unescape(item.get("name", "")).strip()
        if not title:
            continue

        raw_start = item.get("startDate", "")
        raw_end = item.get("endDate", "")
        if not raw_start:
            continue

        try:
            start_date, start_time = _parse_iso(raw_start)
        except (ValueError, AttributeError):
            continue

        end_date: dt.date | None = None
        end_time: dt.time | None = None
        if raw_end:
            try:
                end_date, end_time = _parse_iso(raw_end)
            except (ValueError, AttributeError):
                pass

        # WordPress / The Events Calendar uses startDate=...T00:00:00 +
        # endDate=...T23:59:59 as a sentinel meaning "time not set".
        # Treat this as genuinely unknown time rather than midnight.
        if start_time == dt.time(0, 0) and end_time == dt.time(23, 59, 59):
            start_time = None
            end_time = None

        source_url = item.get("url") or AGENDA_URL
        image_url: str | None = item.get("image") or None
        external_id = _extract_external_id(source_url)

        raw_desc = item.get("description", "")
        description: str | None = None
        price: str | None = None
        if raw_desc:
            description = _strip_html_entities(raw_desc) or None
            if description:
                price = _extract_price(description)

        # Recurrence hint: the regular Monday Jam Session
        recurrence_hint: str | None = None
        if "jam session" in title.lower():
            recurrence_hint = "every Monday"

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                end_date=end_date,
                end_time=end_time,
                source_url=source_url,
                category_slugs=["jazz"],
                price=price,
                description=description,
                image_url=image_url,
                external_id=external_id,
                recurrence_hint=recurrence_hint,
            )
        )

    return events


class JamboreeScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        html = httpx.get(AGENDA_URL, follow_redirects=True, timeout=30).text
        return parse_agenda(html)


register(JamboreeScraper())
