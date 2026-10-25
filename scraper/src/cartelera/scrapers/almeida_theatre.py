"""Almeida Theatre — Islington. New work and reinventions.

The website's performance calendar plus its production pages (see
almeida_theatre_SOURCE.md). Its box office is TNEW (`ticketing.almeida.co.uk`,
see `_tnew`), but the site's calendar already lists every performance with
its TNEW booking link, and more completely (2026-10-25: 189 performances
against TNEW's 150), so TNEW isn't read.

- Calendar: the site's own `admin-ajax.php` call (`action=calendar`, empty
  filters — what `/calendar/` POSTs) → `{"instances": [HTML…]}`: per
  performance `time[datetime="YYYY-MM-DD HH:MM:SS"]`, the production page
  (`a.c-calendar-instance__event-link`), labels
  (`.c-calendar-instance__access-name`: Matinee, Captioned, BSL Interpreted,
  Relaxed Environment, Post Show Talk, season names) and the button
  ("Book Tickets" → `ticketing.almeida.co.uk/<prodSeasonId>/<perfId>`, or a
  disabled "Sold Out").
- Curation: the house is theatre only, but the calendar also sells the
  Theatre Tour. A production page credits its company in a "Cast &
  Creatives" / "Creatives" / "Creative Team" section (`#cast-creatives`,
  `#creatives`, `#creative-team`); the tour's page has none, so a
  performance is kept when its production page has such a section.
- Price: the site publishes none for productions (only "25s & Under £5"
  and schools rates), so price stays unknown unless the page states
  "Tickets £10"; a sold-out performance is "sold-out".
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import _tnew as tnew
from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_BROWSER_UA
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

logger = logging.getLogger(__name__)

VENUE_SLUG = "almeida-theatre"
SITE = "https://almeida.co.uk"
CALENDAR_AJAX = f"{SITE}/admin/wp-admin/admin-ajax.php"
CREDITS_IDS = ("cast-creatives", "creatives", "creative-team")
# Calendar labels worth keeping (season names like "The Inequalities" and
# "Matinee" add nothing).
LABELS = {
    "Captioned": "captioned",
    "BSL Interpreted": "BSL interpreted",
    "Audio Described": "audio described",
    "Relaxed Environment": "relaxed performance",
    "Dementia Friendly": "dementia friendly",
    "Post Show Talk": "post-show talk",
}
_TICKETS = re.compile(r"\bTickets\s*:?\s*(£\s?\d+(?:\.\d{2})?)")


@dataclass
class Slot:
    start: dt.datetime
    url: str  # production page
    title: str
    sold_out: bool
    annotations: list[str] = field(default_factory=list)


@dataclass
class ProductionPage:
    credited: bool
    price: str | None = None
    description: str | None = None
    image_url: str | None = None


def parse_calendar(payload: str) -> list[Slot]:
    data = json.loads(payload)
    instances = data.get("instances") or []
    soup = BeautifulSoup("".join(instances) if isinstance(instances, list) else str(instances), "html.parser")
    slots: list[Slot] = []
    for inst in soup.select(".c-calendar-instance"):
        time_el = inst.select_one("time[datetime]")
        link = inst.select_one("a.c-calendar-instance__event-link[href]")
        if not time_el or not link:
            continue
        try:
            start = dt.datetime.fromisoformat(time_el["datetime"])
        except ValueError:
            logger.warning("almeida: unparseable calendar time %r", time_el.get("datetime"))
            continue
        title_el = inst.select_one(".c-calendar-instance__title")
        button = inst.select_one(".c-calendar-instance__button")
        labels = [tnew.plain(a.get_text(" ")) for a in inst.select(".c-calendar-instance__access-name")]
        slots.append(Slot(
            start=start,
            url=link["href"],
            title=tnew.plain(title_el.get_text(" ")) if title_el else "",
            sold_out=bool(button) and "sold out" in button.get_text(" ").lower() and not button.select_one("a.c-btn--book"),
            annotations=[LABELS[label] for label in labels if label in LABELS],
        ))
    return slots


def parse_production(html: str) -> ProductionPage:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ")
    m = _TICKETS.search(text)
    return ProductionPage(
        credited=any(soup.find(id=i) for i in CREDITS_IDS),
        price=tnew.ladder_price([m.group(1)]) if m else None,
        description=tnew.meta_description(soup),
        image_url=tnew.meta_image(soup),
    )


def build(slots: list[Slot], pages: dict[str, ProductionPage], today: dt.date) -> list[ScrapedEvent]:
    horizon = today + dt.timedelta(days=tnew.WINDOW_DAYS)
    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for slot in slots:
        page = pages.get(slot.url)
        if page is None or not page.credited:
            continue
        slug = slot.url.rstrip("/").rsplit("/", 1)[-1]
        ext = f"{slug}@{slot.start:%Y-%m-%dT%H:%M}"
        if ext in seen or not (today <= slot.start.date() < horizon):
            continue
        seen.add(ext)
        events.append(ScrapedEvent(
            title=slot.title,
            start_date=slot.start.date(),
            start_time=slot.start.time(),
            source_url=slot.url,
            category_slugs=["theater"],
            price="sold-out" if slot.sold_out else page.price,
            description=page.description,
            image_url=page.image_url,
            external_id=ext,
            annotations=slot.annotations,
        ))
    return sorted(events, key=lambda e: (e.start_date, e.start_time, e.title))


def fetch_calendar() -> str:
    with httpx.Client(headers={"User-Agent": CARTELITA_BROWSER_UA}, follow_redirects=True, timeout=tnew.TIMEOUT) as http:
        resp = http.post(CALENDAR_AJAX, data={"action": "calendar", "filters": ""})
        resp.raise_for_status()
        return resp.text


class AlmeidaTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self, today: dt.date | None = None) -> list[ScrapedEvent]:
        today = today or dt.date.today()
        slots = parse_calendar(fetch_calendar())
        html = tnew.fetch_pages(s.url for s in slots)
        pages = {url: parse_production(page) for url, page in html.items()}
        return build(slots, pages, today)


register(
    scraper=AlmeidaTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Almeida Theatre",
        city_slug="london",
        address="Almeida Street, London N1 1TA",
        site_url=SITE,
        instagram_url="https://www.instagram.com/almeidatheatre",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
