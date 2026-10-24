"""Brixton House (ex-Ovalhouse), Coldharbour Lane.

Spektrix client `ovalhouse`, via the shared `_spektrix` helper (see
brixton_house_SOURCE.md). Curation uses two of the box office's own
attributes:

- `Season` — the artistic season ("Season 10") vs "Creative Engagement"
  (the Take Part participation programme: workshops, half-term activities,
  youth sharings, choir), "Hires" and "Commercial" (hires, "Secure My
  Booking"). Only the artistic season is programme;
- `Genre` — New Writing and Youth Theatre (full productions such as Synergy
  Theatre Project's *Providers*; youth sharings sit in Creative Engagement)
  → theater, Family Events → kids. Comedy and Late Night Events (no comedy
  category yet), Live Art (CASA's multi-arts umbrella of exhibitions,
  residencies and parties under one event), Music, Poetry/Spoken Word, Talks
  and Workshops and Community Projects are out. Touch tours and post-show
  Q&As carry no genre.

Show pages on brixtonhouse.co.uk link each performance as
"/book-online/<numeric instance id>", a form the helper's `Site` doesn't
recognise, so this module collects the page ids itself and runs the helper's
remaining steps. The show page also gives the price: its "Tickets: £24 / £20
concessions" line is the public full price, while the Spektrix price list
holds the amount before a per-ticket charge (£21.40 for that £24 ticket).
Titles lose the box office's bracketed run tags ("Providers [2027]").
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.scrapers.price import format_gbp
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "brixton-house"
CLIENT = spk.Client("ovalhouse")
LISTING_URL = "https://brixtonhouse.co.uk/whats-on/"
SHOW_PAGE = re.compile(r"https://brixtonhouse\.co\.uk/shows/[^/\"'<>#?\s]+/")
BOOK_ONLINE = re.compile(r"/book-online/(\d{4,8})\b")
# The first amount of the show page's "Tickets:" line is the full price
# (concessions/schools follow it).
TICKETS = re.compile(r"Tickets:\s*£(\d+(?:\.\d{2})?)")
RUN_TAG = re.compile(r"\s*\[[^\]]*\]\s*$")
ARTISTIC_SEASON = re.compile(r"Season \d+")
GENRES: dict[str, str] = {
    "New Writing": "theater",
    "Youth Theatre": "theater",
    "Family Events": "kids",
}


def categorize(event: dict) -> list[str]:
    if not ARTISTIC_SEASON.fullmatch(spk.attr(event, "Season")):
        return []
    cat = GENRES.get(spk.attr(event, "Genre"))
    return [cat] if cat else []


def title(event: dict) -> str:
    return RUN_TAG.sub("", re.sub(r"\s+", " ", event["name"])).strip()


def page_ids(html: str) -> set[str]:
    """The numeric Spektrix instance ids a show page's booking buttons carry."""
    return set(BOOK_ONLINE.findall(html))


def page_price(html: str) -> str | None:
    """The show page's full ticket price ("Tickets: £24 / £20 concessions" →
    "£24"), None when the page states none."""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    m = TICKETS.search(text)
    return format_gbp(float(m.group(1))) if m else None


def fetch_site() -> dict[str, tuple[set[str], str | None]]:
    """Show-page URL → (its Spektrix instance ids, its stated price)."""
    listing = fetch(LISTING_URL, headers=CARTELITA_BROWSER_HEADERS)
    links = list(dict.fromkeys(SHOW_PAGE.findall(listing)))

    def one(url: str) -> tuple[str, tuple[set[str], str | None]]:
        html = fetch(url, headers=CARTELITA_BROWSER_HEADERS)
        return url, (page_ids(html), page_price(html))

    with ThreadPoolExecutor(max_workers=spk.MAX_CONCURRENCY) as pool:
        return dict(pool.map(one, links))


def with_site_prices(
    events: list[ScrapedEvent], site: dict[str, tuple[set[str], str | None]]
) -> list[ScrapedEvent]:
    """The show page's price wins over the price list's pre-charge amount."""
    out = []
    for ev in events:
        price = (site.get(ev.source_url) or (set(), None))[1]
        out.append(dataclasses.replace(ev, price=price) if price else ev)
    return out


class BrixtonHouseScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with spk.http_client() as http:
            events, instances = spk.fetch_programme(CLIENT, dt.date.today(), http)
            site = fetch_site()
            pages = spk.site_urls({url: ids for url, (ids, _p) in site.items()}, events, instances)
            selected = spk.select(events, instances, categorize)
            prices = spk.fetch_prices(CLIENT, [inst for _e, inst, _c in selected], http)
        built = spk.build(CLIENT, selected, prices, title=title, url=lambda event: pages.get(event["id"]))
        return with_site_prices(built, site)


register(
    scraper=BrixtonHouseScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Brixton House",
        city_slug="london",
        address="385 Coldharbour Lane, London SW9 8GL",
        site_url="https://brixtonhouse.co.uk",
        instagram_url="https://www.instagram.com/brxhousetheatre",
        category_slugs=["theater", "kids"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
