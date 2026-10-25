"""Hampstead Theatre (Main Stage + Downstairs) — Swiss Cottage. New writing.

The website's what's-on, which renders every performance (see
hampstead_theatre_SOURCE.md). Its box office is TNEW
(`my.hampsteadtheatre.com`, see `_tnew`), but the TNEW feed carries only part
of the programme (2026-10-25: 105 performances against the site's 184 —
performances still in priority booking are missing), so the site is the
source and TNEW isn't read.

- Listing `https://www.hampsteadtheatre.com/whats-on/`: one
  `.card--production` per production (title `card__heading`, room
  `card--venue-main-stage` / `card--venue-downstairs`, page link
  `/production/<slug>/`) whose booking dialog lists every performance:
  `li.instances-list__item[data-instances-day=YYYY-MM-DD]` →
  `li.instances-list__time-slot__wrapper[data-time=HH:MM]` with its labels
  (Preview, Press; `data-access` captioned / audio-described) and the
  booking buttons (TNEW links; "Sold Out" on the general-booking button).
- Price: the production page's full-price ladders ("Full price:
  £35/£45/£55/£65", "Previews: £10"), one range over them; concessions
  (Seniors, Under 30s, Access) are left out. Image: the page's og:image.
- Curation: the listing is the programme (the house is theatre only);
  readings or galas sold in TNEW but not listed never show up.
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

VENUE_SLUG = "hampstead-theatre"
SITE = "https://www.hampsteadtheatre.com"
LISTING_URL = f"{SITE}/whats-on/"
PRODUCTION_LINK = re.compile(r"https://www\.hampsteadtheatre\.com/production/[a-z0-9-]+/")
ROOMS = {"card--venue-main-stage": "Main Stage", "card--venue-downstairs": "Downstairs"}
# Instance labels shown to the public that are worth keeping ("Press" nights
# are the box office's business).
LABELS = {"Preview": "preview"}
ACCESS = {"captioned": "captioned", "audio-described": "audio described"}
# "Full price: £35/£45/£55/£65", "Previews: £10" (Downstairs) — the
# full-price ladders, not the Seniors / Under 30s / Access concessions.
_FULL_PRICE = re.compile(r"(?:full price|previews)\s*:\s*((?:£\s?\d+(?:\.\d{2})?\s*/?\s*)+)", re.IGNORECASE)


@dataclass
class Slot:
    start: dt.datetime
    sold_out: bool
    annotations: list[str] = field(default_factory=list)


@dataclass
class Production:
    url: str
    title: str
    room: str
    slots: list[Slot]
    price: str | None = None
    image_url: str | None = None

    @property
    def slug(self) -> str:
        return self.url.rstrip("/").rsplit("/", 1)[-1]


def parse_listing(html: str) -> list[Production]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Production] = []
    for card in soup.select(".card--production"):
        link = next((a["href"] for a in card.select("a[href]") if PRODUCTION_LINK.fullmatch(a["href"])), None)
        heading = card.select_one(".card__heading")
        if not link or not heading:
            continue
        room = next((name for cls, name in ROOMS.items() if cls in (card.get("class") or [])), "")
        slots: list[Slot] = []
        for day in card.select("li.instances-list__item[data-instances-day]"):
            for slot in day.select("li.instances-list__time-slot__wrapper[data-time]"):
                try:
                    start = dt.datetime.fromisoformat(f"{day['data-instances-day']}T{slot['data-time']}")
                except ValueError:
                    logger.warning("hampstead: unparseable slot %s %s", day.get("data-instances-day"), slot.get("data-time"))
                    continue
                general = slot.select_one('cog-booking [data-booking-status~="general-booking"]')
                labels = [LABELS[t] for t in (x.get_text(strip=True) for x in slot.select(".taxonomy-list--instance-type .btn--label")) if t in LABELS]
                labels += [ACCESS[a] for a in (slot.get("data-access") or "").split() if a in ACCESS]
                slots.append(Slot(
                    start=start,
                    sold_out=bool(general) and "sold out" in general.get_text(" ").lower(),
                    annotations=labels,
                ))
        out.append(Production(url=link, title=tnew.plain(heading.get_text(" ")), room=room, slots=slots))
    return out


def parse_price(html: str) -> str | None:
    """A production page's full-price ladders (see _FULL_PRICE) → range."""
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    return tnew.ladder_price(m.group(1) for m in _FULL_PRICE.finditer(text))


def build(productions: list[Production], today: dt.date) -> list[ScrapedEvent]:
    horizon = today + dt.timedelta(days=tnew.WINDOW_DAYS)
    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for prod in productions:
        for slot in prod.slots:
            ext = f"{prod.slug}@{slot.start:%Y-%m-%dT%H:%M}"
            if ext in seen or not (today <= slot.start.date() < horizon):
                continue
            seen.add(ext)
            events.append(ScrapedEvent(
                title=prod.title,
                start_date=slot.start.date(),
                start_time=slot.start.time(),
                source_url=prod.url,
                category_slugs=["theater"],
                price="sold-out" if slot.sold_out else prod.price,
                image_url=prod.image_url,
                external_id=ext,
                annotations=[a for a in dict.fromkeys([prod.room, *slot.annotations]) if a],
            ))
    return sorted(events, key=lambda e: (e.start_date, e.start_time, e.title))


class HampsteadTheatreScraper:
    venue_slug = VENUE_SLUG

    def scrape(self, today: dt.date | None = None) -> list[ScrapedEvent]:
        today = today or dt.date.today()
        productions = parse_listing(fetch(LISTING_URL, headers=CARTELITA_BROWSER_HEADERS))
        pages = tnew.fetch_pages(p.url for p in productions)
        for prod in productions:
            if prod.url in pages:
                prod.price = parse_price(pages[prod.url])
                prod.image_url = tnew.meta_image(BeautifulSoup(pages[prod.url], "html.parser"))
        return build(productions, today)


register(
    scraper=HampsteadTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Hampstead Theatre",
        city_slug="london",
        address="Eton Avenue, Swiss Cottage, London NW3 3EU",
        site_url=SITE,
        instagram_url="https://www.instagram.com/hampsteadtheatre",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
