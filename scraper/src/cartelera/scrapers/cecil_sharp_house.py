"""Cecil Sharp House (Camden) — home of the English Folk Dance and Song
Society (EFDSS): folk gigs, ceilidhs, barn dances, balfolk.

Spektrix client `efdss` on sales.efdss.org, via the shared `_spektrix`
helper (see cecil_sharp_house_SOURCE.md), joined to the what's-on listing of
efdss.org. The box office's own `TAAArtform` label isn't enough: it calls the
weekly Morris Dancing classes "Dance" and leaves several ceilidhs and gigs
unlabelled. The website files every event under its own section, so the
section is the curation:

- **Gigs** (26) and **Dances** (27: ceilidhs, barn dances, balfolk) → folk;
- Classes & Courses (28), Conferences & Talks (61), CPD (66), exhibitions
  and everything else are dropped, as is any Spektrix event the website
  doesn't list.

The join: the listing (`var eeVents = '<json>'` on /whats-on) gives each
item its CMS id, section (`catid`), page and booking link
(`/choose-seats?EventInstanceId=<numeric Spektrix instance id>`); a Spektrix
event matches through its `CMSID` attribute or any of its performances'
ids. Title and page come from the website (the box office's names carry a
season suffix: "The Furrow Collective 2026").

The building: the seating plan → the client's venue "Cecil Sharp House"
(the client also sells events at Band on the Wall, Exeter Phoenix, via
Zoom… which are dropped).
"""

from __future__ import annotations

import html as html_lib
import json
import re

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "cecil-sharp-house"
CLIENT = spk.Client("efdss", "https://sales.efdss.org")
CLIENT_VENUE = "Cecil Sharp House"
SITE = "https://www.efdss.org"
LISTING_URL = f"{SITE}/whats-on"
# The website's what's-on sections kept: Gigs, Dances.
FOLK_SECTIONS = {26, 27}

_EVENTS_VAR = re.compile(r"var eeVents = '(.*?)';\s*$", re.M | re.S)
_INSTANCE_ID = re.compile(r"EventInstanceId=\s*(\d+)")


def parse_listing(page: str) -> list[dict]:
    """The listing's items: the JSON inside a single-quoted JS string."""
    m = _EVENTS_VAR.search(page)
    if not m:
        raise ValueError("efdss.org what's-on: no eeVents listing found")
    # Undo the JS string escapes (\" \' \\), leaving JSON's own escapes.
    return json.loads(re.sub(r"\\(.)", r"\1", m.group(1)))


def site_index(items: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    """(CMS id → item, numeric Spektrix instance id → item)."""
    by_cms: dict[str, dict] = {}
    by_instance: dict[str, dict] = {}
    for item in items:
        by_cms.setdefault(str(item.get("id")), item)
        m = _INSTANCE_ID.search(item.get("bookingLink") or "")
        if m:
            by_instance.setdefault(m.group(1), item)
    return by_cms, by_instance


def join(events: list[dict], instances: list[dict], items: list[dict]) -> dict[str, dict]:
    """Spektrix event id → its website listing item."""
    by_cms, by_instance = site_index(items)
    out: dict[str, dict] = {}
    for event in events:
        item = by_cms.get(spk.attr(event, "CMSID"))
        if item:
            out[event["id"]] = item
    for inst in instances:
        event_id = inst["event"]["id"]
        if event_id not in out and spk.numeric_id(inst["id"]) in by_instance:
            out[event_id] = by_instance[spk.numeric_id(inst["id"])]
    return out


class Programme:
    """Curation, title and page of each Spektrix event, from the listing
    (joined to the programme by `prepare`, before curation)."""

    def __init__(self, items: list[dict]):
        self.items = items
        self.listed: dict[str, dict] = {}

    def prepare(self, events: list[dict], instances: list[dict]) -> None:
        self.listed = join(events, instances, self.items)

    def categorize(self, event: dict) -> list[str]:
        item = self.listed.get(event["id"])
        return ["folk"] if item and item.get("catid") in FOLK_SECTIONS else []

    def title(self, event: dict) -> str:
        item = self.listed.get(event["id"]) or {}
        name = html_lib.unescape(item.get("title") or "").strip() or event["name"]
        return re.sub(r"\s+", " ", name).strip()

    def url(self, event: dict) -> str | None:
        link = (self.listed.get(event["id"]) or {}).get("link") or ""
        return f"{SITE}{link}" if link.startswith("/") else None


def venue(event: dict, instance: dict) -> str | None:
    return VENUE_SLUG if (instance.get("venue") or {}).get("name") == CLIENT_VENUE else None


class CecilSharpHouseScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        programme = Programme(parse_listing(fetch(LISTING_URL, headers=CARTELITA_BROWSER_HEADERS)))
        return spk.scrape(CLIENT, programme.categorize, prepare=programme.prepare, title=programme.title,
                          url=programme.url, venue=venue, plan_venues=True)


register(
    scraper=CecilSharpHouseScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Cecil Sharp House",
        city_slug="london",
        address="2 Regent's Park Road, London NW1 7AY",
        site_url="https://www.efdss.org",
        instagram_url="https://www.instagram.com/efdss",
        category_slugs=["folk"],
        list_memberships=[ListMembership(list_slug="folk")],
    ),
)
