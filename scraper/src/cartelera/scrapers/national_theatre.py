"""National Theatre (Olivier, Lyttelton, Dorfman) — South Bank.

TNEW box office `tickets.nationaltheatre.org.uk` joined to the website's
what's-on (see national_theatre_SOURCE.md and the shared `_tnew` helper):

- TNEW gives every performance (date, time, sold-out status). Its feed also
  sells guided tours, backstage tours, archive tours and "Theatreworks"
  corporate training, which have no production page.
- The website's what's-on (`/whats-on/`) links the production pages
  (`/productions/<slug>/`). A production page links its TNEW production
  ("Dates & tickets" → `events.nationaltheatre.org.uk/events/<id>`), carries
  one JSON-LD `Event` per performance whose `location.name` is the
  auditorium, and a "Ticket prices" ladder in prose.
- Curation: a TNEW performance is kept when its production is linked from a
  production page the what's-on lists AND it plays in one of the three NT
  auditoriums (JSON-LD location of that performance, else the page's
  "The event location is" block). That drops NT work playing elsewhere —
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
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from cartelera.scrapers import _tnew as tnew
from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

logger = logging.getLogger(__name__)

VENUE_SLUG = "national-theatre"
HOST = "tickets.nationaltheatre.org.uk"
# The website's "Dates & tickets" button links this alias of the TNEW host.
BOOKING_HOSTS = (HOST, "events.nationaltheatre.org.uk")
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


def build(perfs: list[tnew.Performance], pages: list[ProductionPage]) -> list[ScrapedEvent]:
    by_production: dict[str, ProductionPage] = {}
    for page in pages:
        for prod in page.productions:
            by_production.setdefault(prod, page)
    events: list[ScrapedEvent] = []
    for perf in perfs:
        page = by_production.get(perf.production_id)
        if page is None:
            continue
        room = page.locations.get(perf.start) or page.location
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
        perfs = tnew.fetch_performances(HOST, today)
        links = listing_links(fetch(LISTING_URL, headers=CARTELITA_BROWSER_HEADERS))
        pages = [parse_production(html, url) for url, html in tnew.fetch_pages(links).items()]
        return build(perfs, pages)


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
