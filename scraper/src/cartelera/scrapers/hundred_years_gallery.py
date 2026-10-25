"""Hundred Years Gallery (Hoxton) — free-improv / experimental music in a
small gallery (Steve Noble, Mark Wastell's residency, the KNOT series).

Own WordPress site. The "Upcoming" page is one server-rendered list of every
item as "Type : Title. Weekday Nth Month HH:MM"; the type prefix is the
site's own structure and is the curation rule: "Music" (incl. "Music /
Poetry") and "Residency" items are kept, exhibitions, books, performance art
and untyped items are dropped. Price, description and image come from each
item's own post. HTTPS times out on this host; plain HTTP is what the site
itself links to. See hundred_years_gallery_SOURCE.md.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_COMPAT_UA
from cartelera.scrapers.price import format_gbp, gbp_amounts
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

logger = logging.getLogger(__name__)

BASE_URL = "http://hundredyearsgallery.co.uk"
LIST_URL = f"{BASE_URL}/events/upcoming/"
VENUE_SLUG = "hundred-years-gallery"
TZ = ZoneInfo("Europe/London")
MAX_CONCURRENCY = 3

KEPT_TYPES = {"music", "residency"}

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# "Music : Title. Sunday 25th October 15.00" — the title may itself contain
# colons ("KNOT #14 : Xiang / ..."), so the type is up to the FIRST colon and
# the date is anchored at the end.
_ITEM_RE = re.compile(
    r"^(?P<type>[^:]+?)\s*:\s*(?P<title>.+?)\.?\s+"
    r"(?P<wd>" + "|".join(_WEEKDAYS) + r")\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(?P<month>[a-z]+)(?:\s+(?P<hh>\d{1,2})[.:](?P<mm>\d{2}))?\s*$",
    re.IGNORECASE,
)


def item_type(text: str) -> str | None:
    m = re.match(r"^([^:.]+?)\s*:", text)
    return m.group(1).strip() if m else None


def is_kept_type(type_label: str | None) -> bool:
    if not type_label:
        return False
    parts = {p.strip().casefold() for p in type_label.split("/")}
    return bool(parts & KEPT_TYPES)


def resolve_date(day: int, month: int, weekday: str, today: dt.date) -> dt.date | None:
    """The list shows no year: take the year (this one or the next) whose
    date falls on the stated weekday, preferring one not in the past."""
    wd = _WEEKDAYS.index(weekday.casefold())
    candidates = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            d = dt.date(year, month, day)
        except ValueError:
            continue
        if d.weekday() == wd:
            candidates.append(d)
    upcoming = [d for d in candidates if d >= today - dt.timedelta(days=7)]
    if upcoming:
        return min(upcoming)
    return None


def parse_item(text: str, href: str, today: dt.date) -> dict | None:
    text = " ".join(text.split())
    m = _ITEM_RE.match(text)
    if not m:
        return None
    month = _MONTHS.get(m.group("month").casefold())
    if not month:
        return None
    date = resolve_date(int(m.group("day")), month, m.group("wd"), today)
    if date is None:
        return None
    time = None
    if m.group("hh"):
        hh, mm = int(m.group("hh")), int(m.group("mm"))
        # "4.30" is an afternoon session: nothing here starts before 9am.
        if 1 <= hh <= 8:
            hh += 12
        if hh < 24 and mm < 60:
            time = dt.time(hh, mm)
    return {
        "type": m.group("type").strip(),
        "title": m.group("title").strip(),
        "start_date": date,
        "start_time": time,
        "href": href,
    }


def parse_upcoming(html: str, today: dt.date) -> list[dict]:
    """The Upcoming page -> kept items (Music / Residency), in page order."""
    soup = BeautifulSoup(html, "html.parser")
    kept: list[dict] = []
    for a in soup.select("h4.petitle a[href]"):
        text = " ".join(a.get_text(" ", strip=True).split())
        if not is_kept_type(item_type(text)):
            continue
        item = parse_item(text, a["href"].strip(), today)
        if item is None:
            logger.warning("hundred_years_gallery: unparseable item %r", text)
            continue
        kept.append(item)
    return kept


_FREE_RE = re.compile(
    r"\bfree\s+(?:event|entry|admission)\b|\b(?:entry|admission)\s*(?:is\s*)?:?\s*free\b",
    re.IGNORECASE,
)
_PRICE_LINE_RE = re.compile(r"door|entry|admission|ticket|cash|£", re.IGNORECASE)


def parse_post(html: str) -> dict:
    """An item's post -> description, price, image."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one(".entry-content")
    if body is None:
        return {}
    paras = [" ".join(p.get_text(" ", strip=True).split()) for p in body.find_all("p")]
    paras = [p for p in paras if p]
    # "free entry, donations welcome" wins over a "suggested donation £5";
    # otherwise the highest £ amount on a door/ticket line ("£10 cash door").
    price = None
    if any(_FREE_RE.search(p) for p in paras):
        price = "free"
    else:
        lines = [p for p in paras if _PRICE_LINE_RE.search(p)]
        amounts = [a for line in lines for a in gbp_amounts(line)]
        if amounts:
            price = format_gbp(max(amounts))
    img = body.find("img")
    image_url = img.get("src") if img and (img.get("src") or "").startswith("http") else None
    return {
        "description": "\n\n".join(paras) or None,
        "price": price,
        "image_url": image_url,
    }


def build_event(item: dict, post: dict | None) -> ScrapedEvent:
    post = post or {}
    t = item["start_time"]
    slug = item["href"].rstrip("/").rsplit("/", 1)[-1]
    return ScrapedEvent(
        title=item["title"],
        start_date=item["start_date"],
        start_time=t,
        start_times=[t] if t else [],
        source_url=item["href"],
        category_slugs=["alternative"],
        price=post.get("price"),
        description=post.get("description"),
        image_url=post.get("image_url"),
        external_id=slug,
        annotations=[item["type"]],
    )


class HundredYearsGalleryScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        today = dt.datetime.now(TZ).date()
        headers = {"User-Agent": CARTELITA_COMPAT_UA}
        with httpx.Client(headers=headers, follow_redirects=True, timeout=30) as client:
            resp = client.get(LIST_URL)
            resp.raise_for_status()
            items = parse_upcoming(resp.text, today)
            if not items:
                raise RuntimeError("hundred_years_gallery: no music items on the Upcoming page")

            def fetch(item: dict) -> dict | None:
                try:
                    r = client.get(item["href"])
                    r.raise_for_status()
                    return parse_post(r.text)
                except httpx.HTTPError as exc:
                    logger.warning("hundred_years_gallery: post fetch failed for %s: %s",
                                   item["href"], exc)
                    return None

            with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
                posts = list(pool.map(fetch, items))
        events: list[ScrapedEvent] = []
        seen: set[str] = set()
        for item, post in zip(items, posts):
            if item["start_date"] < today:
                continue
            ev = build_event(item, post)
            if ev.external_id in seen:
                continue
            seen.add(ev.external_id)
            events.append(ev)
        return events


register(
    HundredYearsGalleryScraper(),
    VenueDefinition(
        slug=VENUE_SLUG,
        name="Hundred Years Gallery",
        city_slug="london",
        address="13 Pearson Street, London E2 8JD",
        site_url="http://hundredyearsgallery.co.uk",
        category_slugs=["alternative"],
        list_memberships=[ListMembership(list_slug="alternative")],
    ),
)
