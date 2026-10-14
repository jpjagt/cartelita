from __future__ import annotations

import datetime as dt
import json
import re

from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers._nl_common import get
from cartelera.scrapers.price import eur_price, format_eur
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# Rotown (Nieuwe Binnenweg, Rotterdam) — pop/indie club + café. A WordPress
# site on the "Theater for WP" plugin; the HOMEPAGE renders the whole upcoming
# programme as `.wp_theatre_event_container` cards, each carrying its own
# schema.org Event JSON-LD (name, url, image, startDate local time, location
# name, offers.price / availability). See rotown_SOURCE.md.
#
# Rotown also promotes shows at other venues (LantarenVenster, Maassilo,
# Annabel, V11, Roodkapje, De Doelen …) — dropped: only `location.name ==
# "Rotown"` is kept (those venues own their listings). Category: the club
# nights carry Rotown's own "ROTOWN NIGHTS" series label → club; everything
# else is a concert → pop. Rotown's free café programme (game nights,
# crafternoons, open mic, record fairs — cards marked "Gratis entree" with no
# ticket offer) is left out: not programme. Price = the JSON-LD offer
# price; for the club nights the show page's "Deur: €7,00" door price (higher
# than the online "vanaf € 5,00") is taken instead — one request per club
# night.
HOME_URL = "https://www.rotown.nl/"
VENUE_SLUG = "rotown"
VENUE_NAME = "Rotown"
CLUB_SERIES = "ROTOWN NIGHTS"

# Rotown types 23:59 when a late-night slot has no real start time.
_PLACEHOLDER_TIME = dt.time(23, 59)


def _text(card: Tag, selector: str) -> str:
    el = card.select_one(selector)
    return el.get_text(" ", strip=True) if el else ""


def _ld(card: Tag) -> dict | None:
    for script in card.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Event":
            return data
    return None


def _offer(ld: dict) -> dict:
    offers = ld.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    return offers if isinstance(offers, dict) else {}


def _price(offer: dict, status: str) -> str | None:
    if "uitverkocht" in status.lower() or "SoldOut" in (offer.get("availability") or ""):
        return "sold-out"
    price = offer.get("price")
    if isinstance(price, (int, float)):
        return "free" if price == 0 else format_eur(float(price))
    if "gratis" in status.lower():
        return "free"
    return eur_price(status, require_symbol=True)  # "Deurverkoop: €7"


def parse_home(html: str, venue_name: str = VENUE_NAME) -> list[ScrapedEvent]:
    """Rotown homepage → ScrapedEvents at `venue_name` (default: Rotown
    itself; the Maassilo scraper reuses this for the shows Rotown programmes
    there). Pure; no network."""
    soup = BeautifulSoup(html, "html.parser")
    events: dict[str, ScrapedEvent] = {}
    for card in soup.select(".wp_theatre_event_container"):
        ld = _ld(card)
        if not ld or not ld.get("startDate") or not ld.get("url"):
            continue
        location = ((ld.get("location") or {}).get("name") or "").strip()
        if location != venue_name:
            continue
        offer = _offer(ld)
        status = _text(card, ".wp_theatre_event_tickets_status")
        if not offer and "gratis" in status.lower():
            continue  # free café programme, not a show
        start = dt.datetime.fromisoformat(ld["startDate"])
        start_time = start.time() if start.time() != _PLACEHOLDER_TIME else None
        subtitle = _text(card, ".wp_theatre_event_subtitle")
        category = "club" if subtitle.upper() == CLUB_SERIES else "pop"
        title = _text(card, ".wp_theatre_event_title") or re.sub(r"\s+", " ", ld.get("name", "")).strip()
        support = _text(card, ".wp_theatre_event_support_title")
        url = ld["url"]
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        external_id = f"{slug}@{start.date().isoformat()}"
        if external_id in events:
            continue  # the homepage repeats featured shows
        annotations = [a for a in (subtitle, support) if a]
        events[external_id] = ScrapedEvent(
            title=title,
            start_date=start.date(),
            start_time=start_time,
            source_url=url,
            category_slugs=[category],
            price=_price(offer, status),
            description=_text(card, ".wp_theatre_event_sounds_like") or None,
            image_url=ld.get("image") or None,
            external_id=external_id,
            annotations=annotations,
        )
    return list(events.values())


_DOOR = re.compile(r"Deur\s*:?\s*€\s*\d+(?:[.,]\d{2}|,-)?", re.IGNORECASE)


def door_price(detail_html: str) -> str | None:
    """The "Deur: €7,00" door price from a show page's remark line, if any."""
    soup = BeautifulSoup(detail_html, "html.parser")
    remark = soup.select_one(".wp_theatre_event_remark")
    m = _DOOR.search(remark.get_text(" ", strip=True)) if remark else None
    return m.group(0) if m else None


def with_door_price(event: ScrapedEvent, detail_html: str) -> ScrapedEvent:
    """Rotown Nights sell online "vanaf € 5,00" but state a higher door price
    on the show page; the price convention shows the highest public price."""
    door = door_price(detail_html)
    if door and event.price not in (None, "sold-out", "free"):
        event.price = eur_price(f"{event.price} {door}")
    return event


class RotownScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        events = parse_home(get(HOME_URL))
        # Door prices differ from the online price on the club nights only
        # (concert pages state a single price + service fee).
        for ev in events:
            if ev.category_slugs == ["club"]:
                with_door_price(ev, get(ev.source_url))
        return events


register(
    scraper=RotownScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name=VENUE_NAME,
        city_slug="rotterdam",
        address="Nieuwe Binnenweg 19, 3014 GA Rotterdam",
        site_url=HOME_URL,
        instagram_url="https://www.instagram.com/rotown",
        category_slugs=["pop", "club"],
        list_memberships=[
            ListMembership(list_slug="pop", whitelist_category_slug="pop"),
            ListMembership(list_slug="club", whitelist_category_slug="club"),
        ],
    ),
)
