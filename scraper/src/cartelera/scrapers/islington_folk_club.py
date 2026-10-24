"""Islington Folk Club — Thursday folk club ("from the fiercely traditional
to the frankly eccentric"), upstairs at the Brewhouse & Kitchen, Highbury
Corner.

A hand-written static site (windows-1252; see islington_folk_club_SOURCE.md):

- `/programme.html` — the programme as tables of Date ("29th October 2026")
  / Artist / Note rows, one guest night each;
- `/ifc.html` (the home page) — the club-wide facts: "the evenings begin at
  8pm" and "Admission … is £10.00 (£8.00 for concessions)".

A single-genre club → folk. Rows whose Artist cell is "Club closed" (the
Christmas-break markers in the table) are not events and are skipped.
"""

from __future__ import annotations

import datetime as dt
import re

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import _yearless, register
from cartelera.scrapers.http import CARTELITA_COMPAT_UA
from cartelera.scrapers.price import gbp_price
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "islington-folk-club"
SITE = "https://www.islingtonfolkclub.co.uk"
PROGRAMME_URL = f"{SITE}/programme.html"
HOME_URL = f"{SITE}/ifc.html"
ENCODING = "cp1252"

_DATE = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _date(text: str) -> dt.date | None:
    m = _DATE.search(text)
    if not m:
        return None
    month = next((n for name, n in _yearless.MONTHS.items() if name.startswith(m.group(2).lower())), None)
    if month is None:
        return None
    try:
        return dt.date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None


def club_facts(home: str) -> tuple[dt.time | None, str | None]:
    """(start time, admission price) from the home page's prose."""
    text = _clean(BeautifulSoup(home, "html.parser").get_text(" "))
    time = None
    m = re.search(r"(?i)evenings begin at ([^.;(]{1,12})", text)
    if m:
        time = _yearless.parse_time(m.group(1))
    price = None
    m = re.search(r"(?i)admission,?[^.£]{0,80}(£[^)]{0,60}\))", text)
    if m:
        price = gbp_price(m.group(1))
    return time, price


def parse(programme: str, today: dt.date, start_time: dt.time | None = None,
          price: str | None = None) -> list[ScrapedEvent]:
    events = []
    for tr in BeautifulSoup(programme, "html.parser").select("table tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        date = _date(cells[0].get_text(" "))
        artist = _clean(cells[1].get_text(" "))
        if not date or not artist or date < today or artist.lower() == "club closed":
            continue
        note = _clean(cells[2].get_text(" ")) if len(cells) > 2 else ""
        events.append(ScrapedEvent(
            title=artist,
            start_date=date,
            start_time=start_time,
            source_url=PROGRAMME_URL,
            category_slugs=["folk"],
            price=price,
            description=note or None,
            external_id=f"ifc-{date.isoformat()}",
        ))
    return events


def _get(client: httpx.Client, url: str) -> str:
    resp = client.get(url)
    resp.raise_for_status()
    return resp.content.decode(ENCODING, errors="replace")


class IslingtonFolkClubScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with httpx.Client(headers={"User-Agent": CARTELITA_COMPAT_UA}, timeout=30, follow_redirects=True) as c:
            programme = _get(c, PROGRAMME_URL)
            time, price = club_facts(_get(c, HOME_URL))
        events = parse(programme, dt.date.today(), time, price)
        if not events and "<table" not in programme:
            raise ValueError("islingtonfolkclub.co.uk: no programme table")
        return events


register(
    scraper=IslingtonFolkClubScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Islington Folk Club",
        city_slug="london",
        address="Brewhouse & Kitchen, 2a Corsica Street, London N5 1JJ",
        site_url=SITE,
        category_slugs=["folk"],
        list_memberships=[ListMembership(list_slug="folk")],
        # The club's own OpenStreetMap link for the pub (geocoding the pub's
        # name would race the club's name).
        lat=51.546256,
        lng=-0.102114,
    ),
)
