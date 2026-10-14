from __future__ import annotations

import datetime as dt
import re

from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers._nl_common import eur_price, first_time, get
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# Baroeg (Spinozaweg, Rotterdam-Lombardijen) — the city's metal/punk/
# hardcore stage since 1984. WordPress + "Theater for WP": `/agenda/` renders
# every upcoming show as a `.wp_theatre_event` card with date ("za 17/10/26"),
# start time, title + production link, Baroeg's own genre list
# (`.wpt_production_category`) and the ticket line ("Vvk € 25,00. Entree €
# 27,50."). One request. See baroeg_SOURCE.md.
#
# Category: Baroeg's night programme — the genre labels "dance night" /
# "Nachtprogramma" (gabber, speedcore, drum'n'bass nights) → club; every other
# show (death/black/doom metal, punk, hardcore, EBM, psych …) → alternative.
# The specific genres go to annotations. Cancelled shows ("Geannuleerd"
# status) and "Baroeg On Tour @ <other venue>" shows are left out.
AGENDA_URL = "https://baroeg.nl/agenda/"
VENUE_SLUG = "baroeg"

CLUB_GENRES = {"dance night", "nachtprogramma"}
_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")
_ON_TOUR = re.compile(r"\bon tour\s*@", re.IGNORECASE)


def _text(card: Tag, selector: str) -> str:
    el = card.select_one(selector)
    return el.get_text(" ", strip=True) if el else ""


def _date(text: str) -> dt.date | None:
    m = _DATE.search(text)
    if not m:
        return None
    day, month, year = (int(g) for g in m.groups())
    if year < 100:
        year += 2000
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def _price(tickets: Tag | None) -> str | None:
    if tickets is None:
        return None
    text = tickets.get_text(" ", strip=True)
    low = text.lower()
    if "uitverkocht" in low or "sold out" in low or tickets.select_one(
        ".wp_theatre_event_tickets_status_soldout"
    ):
        return "sold-out"
    # "… Combitickets: Vvk € 55,00 …" is a multi-day pass, not this show.
    text = re.split(r"combi", text, flags=re.IGNORECASE)[0]
    if "gratis" in low or "free entrance" in low:
        return "free"
    return eur_price(text, require_symbol=True)


def parse_agenda(html: str) -> list[ScrapedEvent]:
    """Baroeg /agenda/ → ScrapedEvents (pure; no network)."""
    soup = BeautifulSoup(html, "html.parser")
    events: dict[str, ScrapedEvent] = {}
    for card in soup.select(".wp_theatre_event"):
        tickets = card.select_one(".wp_theatre_event_tickets")
        if tickets is not None and tickets.select_one(".wp_theatre_event_tickets_status_cancelled"):
            continue
        link = card.select_one(".wp_theatre_event_title a[href]")
        start_date = _date(_text(card, ".wp_theatre_event_startdate"))
        if link is None or start_date is None:
            continue
        title = re.sub(r"\s+", " ", link.get_text(" ", strip=True))
        if not title or _ON_TOUR.search(title):
            continue
        genres = [li.get_text(" ", strip=True) for li in card.select(".wpt_production_category")]
        genres = [g for g in genres if g]
        is_club = any(g.lower() in CLUB_GENRES for g in genres)
        annotations = [g for g in genres if g.lower() not in CLUB_GENRES]
        url = link["href"]
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        external_id = f"{slug}@{start_date.isoformat()}"
        img = card.select_one("figure img[src]")
        events.setdefault(
            external_id,
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=first_time(_text(card, ".wp_theatre_event_starttime")),
                source_url=url,
                category_slugs=["club" if is_club else "alternative"],
                price=_price(tickets),
                description=_text(card, ".wp_theatre_prod_excerpt") or None,
                image_url=img["src"] if img else None,
                external_id=external_id,
                annotations=annotations,
            ),
        )
    return list(events.values())


class BaroegScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return parse_agenda(get(AGENDA_URL))


register(
    scraper=BaroegScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Baroeg",
        city_slug="rotterdam",
        address="Spinozaweg 300, 3076 ET Rotterdam",
        site_url="https://baroeg.nl/",
        instagram_url="https://www.instagram.com/baroegrotterdam",
        category_slugs=["alternative", "club"],
        list_memberships=[
            ListMembership(list_slug="alternative", whitelist_category_slug="alternative"),
            ListMembership(list_slug="club", whitelist_category_slug="club"),
        ],
    ),
)
