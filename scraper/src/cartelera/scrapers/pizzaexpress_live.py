"""PizzaExpress Live — the PizzaExpress Jazz Club in Soho (multi-venue source).

The chain's open JSON API (`api.pizzaexpresslive.com`, the back-end of its
Next.js site) lists every PizzaExpress Live room in one paginated hydra
collection: name, slug, price in pence, seats left, a year-less event date,
doors and show times, and `location` ("Soho", "Holborn", "Chelsea",
"Leicester Square"). The room is the curation rule, read from that field:
only Soho — the long-running jazz club in Dean Street's basement — is kept;
Holborn and Chelsea are tribute/soul/cabaret-led and Leicester Square is a
free piano lounge in a restaurant. Registered as a multi-venue source so
another room can be whitelisted later without a new module.
See pizzaexpress_live_SOURCE.md.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from zoneinfo import ZoneInfo

import httpx

from cartelera.scrapers import register_source
from cartelera.scrapers.http import CARTELITA_COMPAT_UA
from cartelera.scrapers.price import format_gbp
from cartelera.types import ListMembership, ScrapedEvent, SourceDefinition, VenueDefinition

logger = logging.getLogger(__name__)

API_URL = "https://api.pizzaexpresslive.com/products/search-event-information"
SITE_URL = "https://www.pizzaexpresslive.com"
SOURCE_SLUG = "pizzaexpress-live"
TZ = ZoneInfo("Europe/London")
MAX_PAGES = 40

# API `location` -> venue slug (the whitelist).
LOCATIONS: dict[str, str] = {"Soho": "pizzaexpress-jazz-club-soho"}
# Rooms deliberately left out (see SOURCE.md); any other location is logged.
EXCLUDED_LOCATIONS = {"Holborn", "Chelsea", "Leicester Square"}

VENUES = [
    VenueDefinition(
        slug="pizzaexpress-jazz-club-soho",
        name="PizzaExpress Jazz Club Soho",
        city_slug="london",
        address="10 Dean Street, London W1D 3RW",
        site_url=f"{SITE_URL}/pizzaexpress-jazz-club-soho",
        category_slugs=["jazz"],
        list_memberships=[ListMembership(list_slug="jazz")],
    ),
]

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
# "Saturday 24th October"
_DATE_RE = re.compile(r"^([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)$")
# "8:00PM", "1:00PM", "12:00PM"
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*([AP]M)$", re.IGNORECASE)


def parse_date(text: str, today: dt.date) -> dt.date | None:
    """The API's date has no year: take the year (this or next) whose date
    falls on the stated weekday, the first one not before today - 7 days."""
    m = _DATE_RE.match(" ".join((text or "").split()))
    if not m:
        return None
    weekday, day, month = m.group(1).casefold(), int(m.group(2)), _MONTHS.get(m.group(3).casefold())
    if not month or weekday not in _WEEKDAYS:
        return None
    for year in (today.year, today.year + 1, today.year + 2):
        try:
            d = dt.date(year, month, day)
        except ValueError:
            continue
        if d >= today - dt.timedelta(days=7) and d.weekday() == _WEEKDAYS.index(weekday):
            return d
    return None


def parse_time(text: str | None) -> dt.time | None:
    m = _TIME_RE.match((text or "").strip())
    if not m:
        return None
    h, mins, mer = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if not 1 <= h <= 12:
        return None
    return dt.time(h % 12 + (12 if mer == "PM" else 0), mins)


def build_event(item: dict, today: dt.date) -> ScrapedEvent | None:
    """One API item -> an event, or None when its room isn't whitelisted or
    its date can't be read."""
    location = item.get("location") or ""
    venue_slug = LOCATIONS.get(location)
    if venue_slug is None:
        return None
    date = parse_date(item.get("eventDate") or "", today)
    name = " ".join((item.get("name") or "").split())
    slug = item.get("slug") or ""
    if date is None or not name or not slug:
        logger.warning("pizzaexpress_live: unreadable item %r / %r", item.get("eventDate"), name)
        return None
    start = parse_time(item.get("showStartTime"))
    pence = item.get("price")
    if item.get("seatAvailable") == 0:
        price = "sold-out"
    elif isinstance(pence, int):
        price = format_gbp(pence / 100)  # 0 -> "free"
    else:
        price = None
    doors = item.get("doorsOpenTime")
    description = " ".join((item.get("description") or "").split()) or None
    return ScrapedEvent(
        title=name,
        start_date=date,
        start_time=start,
        start_times=[start] if start else [],
        source_url=f"{SITE_URL}/whats-on/{slug}",
        category_slugs=["jazz"],
        price=price,
        description=description,
        image_url=item.get("imageUri") or None,
        # The event SKU is the per-occurrence product variant; the slug is
        # shared by a run of nights (Acoustic Alchemy x12).
        external_id=item.get("eventSku") or f"{slug}@{date.isoformat()}T{start.strftime('%H%M') if start else 'none'}",
        annotations=[f"Doors {doors}"] if doors else [],
        venue_slug=venue_slug,
    )


def events_from_items(items: list[dict], today: dt.date) -> list[ScrapedEvent]:
    unknown = {i.get("location") for i in items} - set(LOCATIONS) - EXCLUDED_LOCATIONS
    if unknown:
        logger.warning("pizzaexpress_live: rooms not in the whitelist (review): %s",
                       ", ".join(sorted(str(u) for u in unknown)))
    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for item in items:
        ev = build_event(item, today)
        if ev is None or ev.start_date < today or ev.external_id in seen:
            continue
        seen.add(ev.external_id)
        events.append(ev)
    return events


class PizzaExpressLiveScraper:
    def scrape(self) -> list[ScrapedEvent]:
        today = dt.datetime.now(TZ).date()
        items: list[dict] = []
        with httpx.Client(headers={"User-Agent": CARTELITA_COMPAT_UA, "Accept": "application/ld+json"},
                          follow_redirects=True, timeout=30) as client:
            for page in range(1, MAX_PAGES + 1):
                resp = client.get(API_URL, params={"page": page})
                resp.raise_for_status()
                data = resp.json()
                items.extend(data.get("hydra:member") or [])
                if not (data.get("hydra:view") or {}).get("hydra:next"):
                    break
        if not items:
            raise RuntimeError("pizzaexpress_live: API returned no events")
        return events_from_items(items, today)


register_source(
    scraper=PizzaExpressLiveScraper(),
    source=SourceDefinition(slug=SOURCE_SLUG, name="PizzaExpress Live", venues=VENUES),
)
