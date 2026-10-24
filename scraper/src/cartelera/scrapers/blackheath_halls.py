"""Blackheath Halls (Blackheath) and Trinity Laban's public venues
(Old Royal Naval College Chapel, Laban Theatre) — one box office.

Spektrix client `blackheathhalls` on events.blackheathhalls.com, via the
shared `_spektrix` helper (see blackheath_halls_SOURCE.md). The client sells
for both organisations, so this is a multi-venue source. Curation on the box
office's own attributes:

- `Category` — free text, but its comma-separated words are exactly the
  website's own filter (Music, Opera, Jazz, Family, Dance, Comedy, Talks,
  Exhibition, Take Part, plus Musical Theatre at Laban): music/opera →
  classical (jazz instead when tagged jazz), family → kids, dance → dance,
  musical theatre → theater. Anything tagged Exhibition, Talks or Take Part
  (courses) is dropped, and so is comedy for adults (no category). An event
  without a Category takes its performances' (instance) Category, which
  Trinity Laban's external concerts carry ("Classical music").
- `Location` — the room/building: Great Hall, The Hearn Recital Room and the
  bars are Blackheath Halls; "The Chapel, Old Royal Naval College" and
  "Laban Theatre" are Trinity Laban's. Anything else (St Michael & All
  Angels, King Charles Court, the Laban Building studios, multi-site
  festival passes) is dropped; a blank Location falls back to
  `EventPostcode` (only the Halls' SE3 9RQ).

Price: the price list (as everywhere); when it can't be had, the box
office's free-text `Price` attribute supplies "free" ("Free, Booking
Required"). The website's show pages carry no Spektrix ids (booking goes
through a WordPress id), so events link to the Spektrix event page.
"""

from __future__ import annotations

import datetime as dt
import re

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register_source
from cartelera.types import ListMembership, ScrapedEvent, SourceDefinition, VenueDefinition

SOURCE_SLUG = "blackheath-halls"
HALLS = "blackheath-halls"
ORNC_CHAPEL = "old-royal-naval-college-chapel"
LABAN = "laban-theatre"
CLIENT = spk.Client("blackheathhalls", "https://events.blackheathhalls.com")

# Category words → ours. "jazz, music" is jazz, not classical.
TOKENS: dict[str, str] = {
    "music": "classical",
    "classical music": "classical",
    "opera": "classical",
    "jazz": "jazz",
    "family": "kids",
    "dance": "dance",
    "musical theatre": "theater",
}
DROP_TOKENS = {"exhibition", "talks", "take part"}

ROOMS: dict[str, str] = {
    "Great Hall": HALLS,
    "The Hearn Recital Room": HALLS,
    "Blackheath Halls": HALLS,
    "Blackheath Halls Bar": HALLS,
    "Café Bar": HALLS,
    "The Chapel, Old Royal Naval College": ORNC_CHAPEL,
    "Old Royal Naval College Chapel": ORNC_CHAPEL,
    "Laban Theatre": LABAN,
}
POSTCODES: dict[str, str] = {"SE3 9RQ": HALLS}
_POSTCODE = re.compile(r"\b([A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})\b")


def tokens(text: str) -> list[str]:
    """"Exhibition, music" → ["exhibition", "music"] (in order, unique)."""
    return list(dict.fromkeys(t.strip().lower() for t in text.split(",") if t.strip()))


def categorize(event: dict) -> list[str]:
    words = tokens(spk.attr(event, "Category"))
    if DROP_TOKENS.intersection(words):
        return []
    cats = list(dict.fromkeys(TOKENS[w] for w in words if w in TOKENS))
    if "jazz" in cats and "classical" in cats:
        cats.remove("classical")
    return cats


def venue(event: dict, instance: dict) -> str | None:
    location = spk.attr(event, "Location") or spk.attr(instance, "Location")
    if location:
        return ROOMS.get(location)
    m = _POSTCODE.search(spk.attr(event, "EventPostcode"))
    return POSTCODES.get(m.group(1)) if m else None


def fill_categories(events: list[dict], instances: list[dict]) -> None:
    """An event without a Category takes its first performance's."""
    by_event: dict[str, str] = {}
    for inst in instances:
        cat = spk.attr(inst, "Category")
        if cat:
            by_event.setdefault(inst["event"]["id"], cat)
    for event in events:
        if not spk.attr(event, "Category") and event["id"] in by_event:
            event["attribute_Category"] = by_event[event["id"]]


def build(selected: list[tuple[dict, dict, list[str]]], prices: dict[str, str | None]) -> list[ScrapedEvent]:
    out = spk.build(CLIENT, selected, prices, venue=venue)
    for scraped, (event, _inst, _cats) in zip(out, selected, strict=True):
        if scraped.price is None and spk.attr(event, "Price").lower().startswith("free"):
            scraped.price = "free"
    return out


class BlackheathHallsScraper:
    def scrape(self) -> list[ScrapedEvent]:
        with spk.http_client() as http:
            events, instances = spk.fetch_programme(CLIENT, dt.date.today(), http)
            fill_categories(events, instances)
            selected = spk.select(events, instances, categorize, venue)
            prices = spk.fetch_prices(CLIENT, [inst for _e, inst, _c in selected], http)
        return build(selected, prices)


def _lists(*cats: str) -> list[ListMembership]:
    return [ListMembership(list_slug=c, whitelist_category_slug=c) for c in cats]


register_source(
    BlackheathHallsScraper(),
    SourceDefinition(
        slug=SOURCE_SLUG,
        name="Blackheath Halls",
        venues=[
            VenueDefinition(
                slug=HALLS,
                name="Blackheath Halls",
                city_slug="london",
                address="23 Lee Road, London SE3 9RQ",
                site_url="https://www.blackheathhalls.com",
                instagram_url="https://www.instagram.com/blackheathhalls",
                category_slugs=["classical", "jazz", "kids", "dance"],
                list_memberships=_lists("classical", "jazz", "kids", "dance"),
            ),
            VenueDefinition(
                slug=ORNC_CHAPEL,
                name="Old Royal Naval College Chapel",
                city_slug="london",
                address="Old Royal Naval College, King William Walk, London SE10 9NN",
                site_url="https://www.ornc.org",
                category_slugs=["classical"],
                list_memberships=[ListMembership(list_slug="classical")],
            ),
            VenueDefinition(
                slug=LABAN,
                name="Laban Theatre",
                city_slug="london",
                address="Creekside, London SE8 3DZ",
                site_url="https://www.trinitylaban.ac.uk",
                category_slugs=["dance", "theater"],
                list_memberships=_lists("dance", "theater"),
            ),
        ],
    ),
)
