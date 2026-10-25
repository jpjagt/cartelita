"""Shakespeare's Globe (Globe Theatre + Sam Wanamaker Playhouse) — Bankside.

The website alone (see shakespeares_globe_SOURCE.md and the shared `_tnew`
helper): the show pages list every performance with its TNEW booking link
(`basket.shakespearesglobe.com/<prodSeasonId>/<perfId>`), date, time and
price. The TNEW feed itself (an Imperva-fronted Tessitura host) never
answers the production server's IP, and the pages carry everything it gave
except the sold-out flag.

- Curation: the website's what's-on groups its cards in sections; only the
  PERFORMANCES section (`section#performances`, sub-headed Globe Theatre /
  Sam Wanamaker Playhouse) is kept. The other sections — Guided Tours,
  Climate Action (MakeBeth, an outdoor Bankside show, is filed here, not
  under Performances), Family Events & Tours, Shakespeare & Race Festival,
  Young People (workshops, courses), Teacher Training (CPD) — and the TNEW
  products the site doesn't list at all (the Exhibition, library visits,
  talks, Telling Tales, touch tours) are dropped.
- A show page's "Dates & Tickets" list (`.c-event-listing`: one per day,
  "FRI 6 NOVEMBER" — no year, see `listing_date`) has one `.c-time-slot`
  per performance: the TNEW link (`…/<prodSeasonId>/<perfId>`; the
  performance id is the external id, as before), the time ("7.30 PM") and
  a price line (`.c-event-listing__price`: "Prices: £89.00 - £29.00* |
  Standing: £5.00, £10.00"; the masthead's "Prices: £89.00 - £5.00" when a
  line is empty).
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from cartelera.scrapers import _tnew as tnew
from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

logger = logging.getLogger(__name__)

VENUE_SLUG = "shakespeares-globe"
HOST = "basket.shakespearesglobe.com"
SITE = "https://www.shakespearesglobe.com"
LISTING_URL = f"{SITE}/whats-on/"
SHOW_LINK = re.compile(r"https://www\.shakespearesglobe\.com/whats-on/[a-z0-9-]+/")
PROGRAMME_SECTION = "section#performances"


_DATE = re.compile(r"(?i)\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?\s+(\d{1,2})\s+([a-z]+)")
_TIME = re.compile(r"(?i)\b(\d{1,2})(?:[.:](\d{2}))?\s*([ap])\.?m\b")
_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass
class ShowPage:
    url: str
    title: str
    productions: set[str]
    prices: dict[str, str | None] = field(default_factory=dict)  # perfId → price
    price: str | None = None  # the masthead's
    room: str = ""
    description: str | None = None
    image_url: str | None = None
    performances: list[tnew.Performance] = field(default_factory=list)


def listing_date(text: str, today: dt.date) -> dt.date | None:
    """"FRI 6 NOVEMBER" → the date: the first of this year and next whose
    weekday matches and that isn't over a week past (a listing never shows
    old dates, and the weekday settles the year)."""
    m = _DATE.search(text)
    month = _MONTHS.get(m.group(3)[:3].lower()) if m else None
    if not m or not month:
        return None
    weekday = _WEEKDAYS.index(m.group(1).lower())
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            day = dt.date(year, month, int(m.group(2)))
        except ValueError:
            continue
        if day.weekday() == weekday and day >= today - dt.timedelta(days=7):
            return day
    return None


def slot_time(text: str) -> dt.time | None:
    """"7.30 PM" → 19:30; "1.00 PM" → 13:00; "12 PM" → 12:00."""
    m = _TIME.search(text)
    if not m:
        return None
    hour = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "p" else 0)
    return dt.time(hour, int(m.group(2) or 0))


def listing_links(html: str) -> list[str]:
    """The show pages of the what's-on PERFORMANCES section."""
    soup = BeautifulSoup(html, "html.parser")
    section = soup.select_one(PROGRAMME_SECTION)
    if section is None:
        raise ValueError("Globe what's-on: no PERFORMANCES section")
    links = [a["href"] for a in section.select("a.c-event-card__cover-link[href]")]
    return [u for u in dict.fromkeys(links) if SHOW_LINK.fullmatch(u)]


def parse_show(html: str, url: str, today: dt.date | None = None) -> ShowPage:
    today = today or dt.date.today()
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one(".c-event-listings h2") or soup.find("h1")
    title = tnew.plain(title_el.get_text(" ")) if title_el else ""
    prices: dict[str, str | None] = {}
    performances: list[tnew.Performance] = []
    for listing in soup.select(".c-event-listing"):
        date_el = listing.select_one(".c-event-listing__date")
        day = listing_date(date_el.get_text(" "), today) if date_el else None
        for slot in listing.select(".c-time-slot"):
            price_el = slot.select_one(".c-event-listing__price")
            price = tnew.ladder_price([price_el.get_text(" ")]) if price_el else None
            link = slot.select_one(f'a[href*="{HOST}/"]')
            time_el = link.select_one("[aria-hidden]") if link else None
            start = slot_time(time_el.get_text(" ")) if time_el else None
            for prod, perf in tnew.booking_ids(str(slot), [HOST]).performances:
                prices[perf] = price
                if day and start:
                    performances.append(tnew.Performance(
                        production_id=prod, performance_id=perf, production_title=title, title=title,
                        start=dt.datetime.combine(day, start), on_sale=True, status="",
                        product_type_id=0, product_type_name="", url=link["href"],
                    ))
    masthead = soup.select_one(".c-masthead__price-label")
    room = soup.select_one(".c-event-locations [role=listitem]")
    return ShowPage(
        url=url,
        title=title,
        productions=tnew.booking_ids(html, [HOST]).all_productions,
        prices=prices,
        price=tnew.ladder_price([masthead.get_text(" ")]) if masthead else None,
        room=tnew.plain(room.get_text(" ")) if room else "",
        description=tnew.meta_description(soup),
        image_url=tnew.meta_image(soup),
        performances=performances,
    )


def build(pages: list[ShowPage], today: dt.date) -> list[ScrapedEvent]:
    """One event per performance the show pages list in [today, today +
    WINDOW_DAYS), each once (a performance id is listed by one page)."""
    horizon = today + dt.timedelta(days=tnew.WINDOW_DAYS)
    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for page in pages:
        for perf in page.performances:
            if perf.performance_id in seen or not (today <= perf.start.date() < horizon):
                continue
            seen.add(perf.performance_id)
            events.append(tnew.event(
                perf,
                title=page.title or perf.production_title,
                source_url=page.url,
                category_slugs=["theater"],
                price=page.prices.get(perf.performance_id) or page.price,
                description=page.description,
                image_url=page.image_url,
                annotations=[page.room] if page.room else [],
            ))
    return sorted(events, key=lambda e: (e.start_date, e.start_time or dt.time(0), e.external_id or ""))


class ShakespearesGlobeScraper:
    venue_slug = VENUE_SLUG

    def scrape(self, today: dt.date | None = None) -> list[ScrapedEvent]:
        today = today or dt.date.today()
        links = listing_links(fetch(LISTING_URL, headers=CARTELITA_BROWSER_HEADERS))
        pages = [parse_show(html, url, today) for url, html in tnew.fetch_pages(links).items()]
        return build(pages, today)


register(
    scraper=ShakespearesGlobeScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Shakespeare's Globe",
        city_slug="london",
        address="21 New Globe Walk, London SE1 9DT",
        site_url=SITE,
        instagram_url="https://www.instagram.com/the_globe",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
