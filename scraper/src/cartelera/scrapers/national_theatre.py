"""National Theatre (Olivier, Lyttelton, Dorfman) — South Bank.

The NT's "date picker" API (`events.nationaltheatre.org.uk/api/v1`, the
booking calendar its "Dates & tickets" button opens; TNEW ids) joined to the
website's what's-on (see national_theatre_SOURCE.md and the shared `_tnew`
helper):

- The picker gives every performance of a TNEW production (`/events/<id>`:
  TNEW performance id, start, auditorium, booking status incl. sold out).
  It replaces the TNEW feed of `tickets.nationaltheatre.org.uk`, which (an
  Imperva-fronted Tessitura host) never answers the production server's IP.
  Guided tours, backstage tours, archive tours and "Theatreworks" corporate
  training are TNEW products without a production page, so never asked.
- The website's what's-on (`/whats-on/`) links the production pages
  (`/productions/<slug>/`). A production page links its TNEW production
  ("Dates & tickets" → `events.nationaltheatre.org.uk/events/<id>`), carries
  one JSON-LD `Event` per performance whose `location.name` is the
  auditorium, and a "Ticket prices" ladder in prose.
- Curation: a performance is kept when its production is linked from a
  production page the what's-on lists AND it plays in one of the three NT
  auditoriums (the picker's venue of that performance, else the page's
  JSON-LD location, else its "The event location is" block). That drops NT work playing elsewhere —
  West End transfers (Hadestown at the Lyric, The History Boys at the
  Haymarket, Pride at the Bridge), Broadway (Inter Alia), UK tours — whose
  pages are listed but locate elsewhere (they aren't sold on the NT's TNEW
  either), NT Live cinema screenings (ntlive.com) and NT at Home streams.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import _tnew as tnew
from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, CARTELITA_COMPAT_UA, fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

logger = logging.getLogger(__name__)

VENUE_SLUG = "national-theatre"
HOST = "tickets.nationaltheatre.org.uk"
# The website's "Dates & tickets" button links this alias of the TNEW host.
BOOKING_HOSTS = (HOST, "events.nationaltheatre.org.uk")
# The booking calendar behind "Dates & tickets" (CloudFront, open).
PICKER_API = "https://events.nationaltheatre.org.uk/api/v1"
SITE = "https://www.nationaltheatre.org.uk"
LISTING_URL = f"{SITE}/whats-on/"
PRODUCTION_LINK = re.compile(r"https://www\.nationaltheatre\.org\.uk/productions/[a-z0-9-]+/")
AUDITORIUMS = {"Olivier Theatre": "Olivier", "Lyttelton Theatre": "Lyttelton", "Dorfman Theatre": "Dorfman"}
# A ladder line once its label is cut: only £ amounts and separators.
_LADDER = re.compile(r"(?:£\s?\d+(?:\.\d{2})?[\s,/&–-]*)+")


@dataclass
class ProductionPage:
    url: str
    productions: set[str]  # TNEW production ids the page links
    location: str  # the page's own "event location" (first line)
    locations: dict[dt.datetime, str] = field(default_factory=dict)  # JSON-LD start → auditorium
    price: str | None = None
    title: str | None = None
    description: str | None = None
    image_url: str | None = None


def listing_links(html: str) -> list[str]:
    return list(dict.fromkeys(m.group(0) for m in PRODUCTION_LINK.finditer(html)))


def _json_ld_events(soup: BeautifulSoup) -> list[dict]:
    out: list[dict] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and "Event" in str(item.get("@type")):
                out.append(item)
    return out


def ticket_price(soup: BeautifulSoup) -> str | None:
    """The "Ticket prices" block's ladders ("Monday – Thursday … : £25, £36,
    £51, £72, £93", "Previews … : £20, …") → one range over all of them.
    Lines with prose around the amounts (the booking fee) don't count."""
    heading = next((h for h in soup.find_all(["h2", "h3", "h4"])
                    if h.get_text(" ", strip=True).lower() == "ticket prices"), None)
    if heading is None:
        return None
    lines: list[str] = []
    for sib in heading.find_next_siblings():
        if sib.name in ("h2", "h3", "h4"):
            break
        text = sib.get_text(" ", strip=True)
        amounts = text.rsplit(":", 1)[-1].strip()
        if amounts and _LADDER.fullmatch(amounts):
            lines.append(amounts)
    return tnew.ladder_price(lines)


def parse_production(html: str, url: str) -> ProductionPage:
    soup = BeautifulSoup(html, "html.parser")
    events = _json_ld_events(soup)
    locations: dict[dt.datetime, str] = {}
    for ev in events:
        try:
            start = dt.datetime.fromisoformat(ev["startDate"]).astimezone(tnew.LONDON).replace(tzinfo=None)
        except (KeyError, TypeError, ValueError):
            continue
        locations[start] = tnew.plain((ev.get("location") or {}).get("name"))
    venue = soup.select_one(".c-event-details__venue-details") or soup.select_one(".c-event-details__venue")
    location = ""
    if venue:
        parts = [p for p in venue.get_text("\n", strip=True).split("\n") if p and "event location" not in p.lower()]
        location = tnew.plain(parts[0]) if parts else ""
    first = events[0] if events else {}
    image = first.get("image")
    if isinstance(image, str):
        image = image.split("?resize=")[0]  # a 150px thumbnail of the full image
    return ProductionPage(
        url=url,
        productions=tnew.booking_ids(html, BOOKING_HOSTS).all_productions,
        location=location,
        locations=locations,
        price=ticket_price(soup),
        title=tnew.plain(first.get("name")) or None,
        description=tnew.plain(first.get("description")) or tnew.meta_description(soup),
        image_url=(image[0] if isinstance(image, list) and image else image) or tnew.meta_image(soup),
    )


def picker_performances(
    data: dict, today: dt.date
) -> tuple[list[tnew.Performance], dict[str, str]]:
    """A picker `/events/<id>` response → (its performances in [today, today
    + WINDOW_DAYS), in start order; performance id → auditorium). One per
    (production, start), as the TNEW feed."""
    horizon = today + dt.timedelta(days=tnew.WINDOW_DAYS)
    prod_id = str(data["_id"])
    title = tnew.plain(data.get("title"))
    perfs: list[tnew.Performance] = []
    rooms: dict[str, str] = {}
    seen: set[dt.datetime] = set()
    for inst in data.get("instances") or []:
        try:
            start = dt.datetime.fromisoformat(inst["datetime"]).astimezone(tnew.LONDON).replace(tzinfo=None)
        except (KeyError, TypeError, ValueError):
            continue
        if not (today <= start.date() < horizon) or start in seen:
            continue
        seen.add(start)
        status = str(inst.get("bookingStatus") or "").lower()
        perf = tnew.Performance(
            production_id=prod_id,
            performance_id=str(inst["_id"]),
            production_title=title,
            title=title,
            start=start,
            on_sale=status not in ("notonsale", "soldout"),
            status="Sold out" if status == "soldout" else "",
            product_type_id=0,
            product_type_name="",
            url=inst.get("bookingURL") or "",
            image_url=data.get("thumbnail") or None,
        )
        perfs.append(perf)
        rooms[perf.performance_id] = tnew.plain(inst.get("venue"))
    return sorted(perfs, key=lambda p: p.start), rooms


def fetch_picker(production_ids: Iterable[str], today: dt.date) -> tuple[list[tnew.Performance], dict[str, str]]:
    """Every picker performance of `production_ids` (see picker_performances).
    A production the picker doesn't know (404) is skipped with a warning;
    any other failure fails the run."""
    perfs: list[tnew.Performance] = []
    rooms: dict[str, str] = {}
    with httpx.Client(headers={"User-Agent": CARTELITA_COMPAT_UA, "Accept": "application/json"},
                      follow_redirects=True, timeout=tnew.TIMEOUT) as http:
        for prod_id in sorted(set(production_ids)):
            resp = http.get(f"{PICKER_API}/events/{prod_id}")
            if resp.status_code == 404:
                logger.warning("national theatre: picker has no production %s", prod_id)
                continue
            resp.raise_for_status()
            found, found_rooms = picker_performances(resp.json(), today)
            perfs += found
            rooms.update(found_rooms)
    return sorted(perfs, key=lambda p: (p.start, p.production_id)), rooms


def build(
    perfs: list[tnew.Performance], pages: list[ProductionPage], rooms: dict[str, str] | None = None
) -> list[ScrapedEvent]:
    """`rooms`: performance id → auditorium (the picker's), ahead of the
    page's JSON-LD / venue block."""
    rooms = rooms or {}
    by_production: dict[str, ProductionPage] = {}
    for page in pages:
        for prod in page.productions:
            by_production.setdefault(prod, page)
    events: list[ScrapedEvent] = []
    for perf in perfs:
        page = by_production.get(perf.production_id)
        if page is None:
            continue
        room = rooms.get(perf.performance_id) or page.locations.get(perf.start) or page.location
        if room not in AUDITORIUMS:
            continue
        events.append(tnew.event(
            perf,
            title=page.title or perf.production_title,
            source_url=page.url,
            category_slugs=["theater"],
            price=page.price,
            description=page.description,
            image_url=page.image_url,
            annotations=[AUDITORIUMS[room]],
        ))
    return events


class NationalTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self, today: dt.date | None = None) -> list[ScrapedEvent]:
        today = today or dt.date.today()
        links = listing_links(fetch(LISTING_URL, headers=CARTELITA_BROWSER_HEADERS))
        pages = [parse_production(html, url) for url, html in tnew.fetch_pages(links).items()]
        perfs, rooms = fetch_picker((prod for page in pages for prod in page.productions), today)
        return build(perfs, pages, rooms)


register(
    scraper=NationalTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="National Theatre",
        city_slug="london",
        address="Upper Ground, London SE1 9PX",
        site_url=SITE,
        instagram_url="https://www.instagram.com/nationaltheatre",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
