"""Green Note (Camden) — small folk, roots and americana venue: a nightly
show upstairs and gigs in its Basement Bar.

WordPress with the "Theater for WordPress" plugin (see green_note_SOURCE.md).
The listing `/events-page/` renders every upcoming event
(`.wp_theatre_event`): title + production link, date ("Mon 26th October"
— no year, no time), room (`.wp_theatre_event_venue`), remark, ticket link,
price ("£ 15.00") and a status for cancelled/sold-out events. The start
time is only on the production page (one request per production; its own
`.wp_theatre_event` blocks read "Tue 27th October 7:00pm").

Curation: the venue is single-genre (folk/roots) → folk, and only its own
rooms count — "GREEN NOTE" and "THE BASEMENT BAR". Green Note Presents
shows at other venues (The Water Rats, St Pancras Old Church, Heath Street
Baptist Church, The Lexington, or no room given) and cancelled events are
dropped. The year comes from the weekday (`_yearless`, anchored on today).
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup

from cartelera.scrapers import _yearless, register
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.scrapers.price import gbp_price
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

logger = logging.getLogger(__name__)

VENUE_SLUG = "green-note"
SITE = "https://www.greennote.co.uk"
LISTING_URL = f"{SITE}/events-page/"
ROOMS = {"GREEN NOTE", "THE BASEMENT BAR"}
MAX_CONCURRENCY = 3


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_listing(page: str, today: dt.date) -> list[dict]:
    """Every listing row: title, url, date, room, price, status, remark,
    image."""
    rows = []
    for ev in BeautifulSoup(page, "html.parser").select(".wp_theatre_event"):
        link = ev.select_one(".wp_theatre_event_title a[href]")
        when = ev.select_one(".wp_theatre_event_datetime")
        if not link or not when:
            continue
        room = ev.select_one(".wp_theatre_event_venue")
        price = ev.select_one(".wp_theatre_event_prices")
        status = ev.select_one(".wp_theatre_event_tickets_status")
        remark = ev.select_one(".wp_theatre_event_remark")
        image = ev.select_one("figure img[src]")
        rows.append({
            "title": _clean(link.get_text(" ")),
            "url": link["href"],
            "date": _yearless.parse(when.get_text(" "), today),
            "room": _clean(room.get_text(" ")).upper() if room else "",
            "price": _clean(price.get_text(" ")) if price else "",
            "status": " ".join(status.get("class") or []) + " " + _clean(status.get_text(" ")) if status else "",
            "remark": _clean(remark.get_text(" ")) if remark else "",
            "image": image["src"] if image else None,
        })
    return rows


def production_times(page: str, today: dt.date) -> dict[dt.date, dt.time]:
    """A production page → start time per date (its `.wp_theatre_event`
    blocks: "Tue 27th October 7:00pm")."""
    out: dict[dt.date, dt.time] = {}
    for ev in BeautifulSoup(page, "html.parser").select(".wp_theatre_event_datetime"):
        text = ev.get_text(" ")
        date, time = _yearless.parse(text, today), _yearless.parse_time(text)
        if date and time:
            out.setdefault(date, time)
    return out


def _price(row: dict) -> str | None:
    status = row["status"].lower()
    if "sold" in status:
        return "sold-out"
    found = gbp_price(row["price"])
    if found:
        return found
    return "free" if re.search(r"(?i)\bfree\b", row["price"]) else None


def kept(rows: list[dict], today: dt.date) -> list[dict]:
    return [
        r for r in rows
        if r["room"] in ROOMS and r["date"] and r["date"] >= today and "cancel" not in r["status"].lower()
    ]


def parse(rows: list[dict], times: dict[str, dict[dt.date, dt.time]], today: dt.date) -> list[ScrapedEvent]:
    """Kept listing rows → ScrapedEvents; `times`: production URL →
    production_times()."""
    events: list[ScrapedEvent] = []
    seen: dict[str, int] = {}
    for row in kept(rows, today):
        slug = row["url"].rstrip("/").rsplit("/", 1)[-1]
        key = f"{slug}@{row['date'].isoformat()}"
        seen[key] = seen.get(key, 0) + 1
        events.append(ScrapedEvent(
            title=row["title"],
            start_date=row["date"],
            start_time=times.get(row["url"], {}).get(row["date"]),
            source_url=row["url"],
            category_slugs=["folk"],
            price=_price(row),
            description=row["remark"] or None,
            image_url=row["image"],
            external_id=key if seen[key] == 1 else f"{key}#{seen[key]}",
            annotations=["Basement Bar"] if row["room"] == "THE BASEMENT BAR" else [],
        ))
    return events


def fetch_times(urls: list[str], today: dt.date) -> dict[str, dict[dt.date, dt.time]]:
    """Production URL → its start times; a page that fails leaves that
    production's times unknown."""

    def one(url: str) -> tuple[str, dict[dt.date, dt.time]]:
        try:
            return url, production_times(fetch(url, headers=CARTELITA_BROWSER_HEADERS), today)
        except Exception as exc:  # the time is optional, never a failed run
            logger.warning("greennote.co.uk: no times from %s (%s)", url, exc)
            return url, {}

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        return dict(pool.map(one, urls))


class GreenNoteScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        today = dt.date.today()
        rows = parse_listing(fetch(LISTING_URL, headers=CARTELITA_BROWSER_HEADERS), today)
        if not rows:
            raise ValueError("greennote.co.uk: no events on the listing")
        urls = list(dict.fromkeys(r["url"] for r in kept(rows, today)))
        return parse(rows, fetch_times(urls, today), today)


register(
    scraper=GreenNoteScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Green Note",
        city_slug="london",
        address="106 Parkway, London NW1 7AN",
        site_url=SITE,
        instagram_url="https://www.instagram.com/greennotecamden",
        category_slugs=["folk"],
        list_memberships=[ListMembership(list_slug="folk")],
    ),
)
