from __future__ import annotations

import datetime as dt
import html as html_module
import json
import re

from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.scrapers._eur import HEADERS, eur_amounts, format_eur, to_float
from cartelera.scrapers.http import fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# De Helling (Helling 7, Utrecht-Rotsoord) — pop venue with concerts and club
# nights. The agenda page server-renders every upcoming event as a
# `.c-event-card` with an embedded schema.org Event JSON-LD (name, url, image,
# start, offers.price, eventStatus) plus the venue's genre
# tags in `.c-event-card__meta li` (after the weekday-date and doors-time items).
#
# Category discriminator: the agenda's own "type" filter (`?label[]=club`,
# server-side), the venue's section split between club nights and concerts. We
# fetch the club-filtered list and mark those cards club, the rest pop. The
# `label[]=cafe` filter (café/bar nights) is fetched too and left out.
# See de_helling_SOURCE.md.
BASE_URL = "https://dehelling.nl"
AGENDA_URL = f"{BASE_URL}/agenda/"
CLUB_URL = f"{AGENDA_URL}?label%5B%5D=club"
CAFE_URL = f"{AGENDA_URL}?label%5B%5D=cafe"
VENUE_SLUG = "de-helling"

# eventStatus values seen: "Geen" (none), "Uitverkocht", "Afgelast".
_CANCELLED = {"afgelast", "geannuleerd"}
_SOLD_OUT = {"uitverkocht"}


def card_ids(html: str) -> set[str]:
    """The card ids (per-occurrence slugs) on an agenda page."""
    soup = BeautifulSoup(html, "html.parser")
    return {c["id"] for c in soup.select(".c-event-card[id]")}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html_module.unescape(text)).strip()


def _price(offers: dict, status: str) -> str | None:
    # Only the venue's own eventStatus "Uitverkocht" means sold out:
    # offers.availability says SoldOut for many on-sale events (the detail
    # page shows a live "Tickets" button), so it is ignored.
    if status.lower() in _SOLD_OUT:
        return "sold-out"
    raw = offers.get("price")
    if raw in (None, ""):
        return None
    try:
        return format_eur(to_float(str(raw)))
    except ValueError:
        return None


def detail_price(html: str) -> str | None:
    """The detail page's "Prijs" field ("€29,50" / "Gratis"). Used only for
    cards whose JSON-LD has no offers.price (free events)."""
    soup = BeautifulSoup(html, "html.parser")
    lines = [ln for ln in (_clean(x) for x in soup.get_text("\n").split("\n")) if ln]
    for label, value in zip(lines, lines[1:]):
        if label.lower() != "prijs":
            continue
        low = value.lower()
        if "uitverkocht" in low:
            return "sold-out"
        if "gratis" in low or "free" in low:
            return "free"
        amounts = eur_amounts(value)
        if amounts:
            return format_eur(max(amounts))
    return None


def parse_agenda(
    html: str, club_ids: set[str], cafe_ids: set[str] | None = None
) -> list[ScrapedEvent]:
    cafe_ids = cafe_ids or set()
    soup = BeautifulSoup(html, "html.parser")
    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for card in soup.select(".c-event-card[id]"):
        card_id = card["id"]
        if card_id in seen or card_id in cafe_ids:
            continue
        script = card.select_one('script[type="application/ld+json"]')
        if script is None or not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        status = str(data.get("eventStatus") or "")
        if status.lower() in _CANCELLED:
            continue
        start_raw = data.get("startDate")
        title = _clean(data.get("name") or "")
        url = data.get("url")
        if not (start_raw and title and url):
            continue
        start = dt.datetime.strptime(start_raw, "%Y-%m-%d %H:%M:%S")
        seen.add(card_id)
        meta = [_clean(li.get_text(" ")) for li in card.select(".c-event-card__meta li")]
        events.append(
            ScrapedEvent(
                title=title,
                start_date=start.date(),
                start_time=start.time(),
                source_url=url,
                category_slugs=["club"] if card_id in club_ids else ["pop"],
                price=_price(data.get("offers") or {}, status),
                image_url=data.get("image") or None,
                external_id=card_id,
                annotations=[m for m in meta[2:] if m],
            )
        )
    return events


class DeHellingScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        agenda = fetch(AGENDA_URL, headers=HEADERS)
        club_ids = card_ids(fetch(CLUB_URL, headers=HEADERS))
        cafe_ids = card_ids(fetch(CAFE_URL, headers=HEADERS))
        events = parse_agenda(agenda, club_ids, cafe_ids)
        for ev in events:
            if ev.price is None:
                ev.price = detail_price(fetch(ev.source_url, headers=HEADERS))
        return events


register(
    scraper=DeHellingScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="De Helling",
        city_slug="utrecht",
        address="Helling 7, 3523 CB Utrecht",
        site_url=BASE_URL,
        instagram_url="https://www.instagram.com/dehelling",
        category_slugs=["pop", "club"],
        list_memberships=[
            ListMembership(list_slug="pop", whitelist_category_slug="pop"),
            ListMembership(list_slug="club", whitelist_category_slug="club"),
        ],
    ),
)
