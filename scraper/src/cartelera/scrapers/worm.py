from __future__ import annotations

import datetime as dt
import logging
import re

from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.scrapers._nl_common import ENGLISH_MONTHS, first_time, get
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# WORM (Boomgaardsstraat, Rotterdam) — institute for avant-garde
# recreation: experimental/underground concerts, club nights, cinema,
# performance. WordPress + "Theater for WP" (productions under /production/);
# `/agenda/` lists every upcoming item as an `.agenda-item` under month
# headers ("October 2026"), with title, "Wed 14 October" and WORM's own
# category label (`.agenda-item__title__cat`). The start time lives only on
# the production page ("Start → 20:30"). See worm_SOURCE.md.
#
# Category = WORM's own label: FIlm → film; Club → club; Concert, Theatre /
# Performance, Festival → alternative. Community, Workshop, Talk, Broadcast /
# Stream and Art & expo items (sewing/drawing clubs, singing club, talks,
# radio broadcasts, expos) are not programme for us and are left out. Price
# is only on Stager (which disallows bots) → None.
AGENDA_URL = "https://worm.org/agenda/"
VENUE_SLUG = "worm"

CATEGORY_MAP = {
    "film": "film",
    "club": "club",
    "concert": "alternative",
    "theatre / performance": "alternative",
    "festival": "alternative",
}
EXCLUDED = {"community", "workshop", "talk", "broadcast / stream", "art & expo"}

logger = logging.getLogger(__name__)

_MONTH_HEADER = re.compile(r"([A-Za-z]+)\s+(\d{4})")
_DAY_MONTH = re.compile(r"(\d{1,2})\s+([A-Za-z]+)")
_FULL_DATE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
_START = re.compile(r"Start\s*→\s*(\d{1,2}[:.]\d{2})")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_agenda(html: str) -> list[dict]:
    """`/agenda/` → [{url, title, label, date, image}] in page order (pure)."""
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    year: int | None = None
    month_of_header: int | None = None
    for el in soup.select(".agenda__month__month, .agenda-item"):
        if "agenda__month__month" in (el.get("class") or []):
            m = _MONTH_HEADER.search(_clean(el.get_text(" ")))
            if m and m.group(1).lower() in ENGLISH_MONTHS:
                month_of_header = ENGLISH_MONTHS[m.group(1).lower()]
                year = int(m.group(2))
            continue
        link = el.select_one("a.agenda-item__link[href]")
        title_el = el.select_one(".agenda-item__title__title")
        date_el = el.select_one(".agenda-item__title__date")
        if not (link and title_el and date_el and year):
            continue
        m = _DAY_MONTH.search(_clean(date_el.get_text(" ")))
        if not m or m.group(2).lower() not in ENGLISH_MONTHS:
            continue
        month = ENGLISH_MONTHS[m.group(2).lower()]
        # An item spilling past its month header's year (December header,
        # January item) rolls over.
        y = year + 1 if month_of_header and month < month_of_header else year
        try:
            date = dt.date(y, month, int(m.group(1)))
        except ValueError:
            continue
        label_el = el.select_one(".agenda-item__title__cat")
        img = el.select_one(".agenda-item__thumbnail img[src]")
        items.append({
            "url": link["href"],
            "title": _clean(title_el.get_text(" ")),
            "label": _clean(label_el.get_text(" ")) if label_el else "",
            "date": date,
            "image": img["src"] if img else None,
        })
    return items


def category_for(label: str) -> str | None:
    """WORM's label → our category; None for non-programme labels."""
    key = label.strip().lower()
    if key in CATEGORY_MAP:
        return CATEGORY_MAP[key]
    if key not in EXCLUDED:
        logger.warning("worm: unknown agenda label %r — skipped", label)
    return None


def parse_detail(html: str) -> tuple[dt.date | None, dt.time | None]:
    """A production page → (date, start time) from its meta block (pure)."""
    soup = BeautifulSoup(html, "html.parser")
    date = None
    date_el = soup.select_one(".agenda-single-meta__date")
    if date_el:
        m = _FULL_DATE.search(_clean(date_el.get_text(" ")))
        if m and m.group(2).lower() in ENGLISH_MONTHS:
            try:
                date = dt.date(int(m.group(3)), ENGLISH_MONTHS[m.group(2).lower()], int(m.group(1)))
            except ValueError:
                date = None
    start = None
    start_el = soup.select_one(".agenda-single-meta__start")
    if start_el:
        m = _START.search(_clean(start_el.get_text(" ")))
        start = first_time(m.group(1)) if m else None
    return date, start


def build_events(agenda_html: str, details: dict[str, str]) -> list[ScrapedEvent]:
    """Agenda items + their production pages (url → html) → ScrapedEvents.
    A missing detail page leaves the time unknown (pure)."""
    events: dict[str, ScrapedEvent] = {}
    for item in parse_agenda(agenda_html):
        category = category_for(item["label"])
        if category is None:
            continue
        date, start = (None, None)
        if item["url"] in details:
            date, start = parse_detail(details[item["url"]])
        date = date or item["date"]
        slug = item["url"].rstrip("/").rsplit("/", 1)[-1]
        external_id = f"{slug}@{date.isoformat()}"
        events.setdefault(external_id, ScrapedEvent(
            title=item["title"],
            start_date=date,
            start_time=start,
            source_url=item["url"],
            category_slugs=[category],
            image_url=item["image"],
            external_id=external_id,
            annotations=[item["label"]] if category == "alternative" else [],
        ))
    return list(events.values())


def detail_urls(agenda_html: str) -> list[str]:
    """Production pages worth fetching: programme items only."""
    return list(dict.fromkeys(
        i["url"] for i in parse_agenda(agenda_html) if category_for(i["label"])
    ))


class WormScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        agenda = get(AGENDA_URL)
        details = {url: get(url) for url in detail_urls(agenda)}
        return build_events(agenda, details)


register(
    scraper=WormScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="WORM",
        city_slug="rotterdam",
        address="Boomgaardsstraat 71, 3012 XA Rotterdam",
        site_url="https://worm.org/",
        instagram_url="https://www.instagram.com/wormrotterdam",
        category_slugs=["alternative", "film", "club"],
        list_memberships=[
            ListMembership(list_slug="alternative", whitelist_category_slug="alternative"),
            ListMembership(list_slug="film", whitelist_category_slug="film"),
            ListMembership(list_slug="club", whitelist_category_slug="club"),
        ],
    ),
)
