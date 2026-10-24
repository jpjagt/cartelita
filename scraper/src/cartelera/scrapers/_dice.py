"""DICE (dice.fm) — shared by the London gig and club venues that sell on it.

Two ways in, per venue (see dice_london_SOURCE.md):

- **The venue's own widget key.** A venue that embeds DICE's event-list
  widget on its own site publishes a partner key for it. With *that* key we
  fetch *that* venue's events only — exactly what its public widget shows —
  from `partners-endpoint.dice.fm/api/v2/events?filter[venues][]=<name>`:
  every upcoming event, with DICE's type tags (`music:gig`, `music:dj`,
  `culture:comedy` …), genre tags (`gig:indie`, `gig:punk` …), ticket prices
  and status. A key is never used for another venue.
- **The public venue page** `dice.fm/venue/<page>`: its `__NEXT_DATA__` lists
  the next 30 events (date, status, price incl. fees); each event's own page
  `dice.fm/event/<id>` adds the type tags and the description. One request
  per event.

Curation is DICE's own **type tag**, mapped per venue to our category (types
a venue doesn't map — comedy, quizzes, parties at a gig venue — are dropped);
with a key, a venue may refine the category by **genre tag** (e.g. a punk
gig → rock). Cancelled events are dropped.

Private module (leading underscore): skipped by `load_all()`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

import httpx

from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, CARTELITA_COMPAT_UA
from cartelera.scrapers.price import format_gbp_range
from cartelera.types import ScrapedEvent

API = "https://partners-endpoint.dice.fm/api/v2/events"
SITE = "https://dice.fm"
LONDON = ZoneInfo("Europe/London")
PAGE_SIZE = 100
MAX_PAGES = 10
# Event pages fetched at once in public mode.
MAX_CONCURRENCY = 3
TIMEOUT = 60

_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


@dataclass(frozen=True)
class Venue:
    """One of our venues as DICE knows it.

    `types`: DICE type tag → our category; events whose type tags map to
    nothing are dropped. `genres` (key mode only): genre tag → category,
    overriding the type mapping when the event carries one. `api_key` is the
    venue's own published widget key and `key_origin` the page publishing
    it (recorded so the key can be re-checked when it rotates)."""

    slug: str
    dice_name: str
    page: str
    types: dict[str, str]
    genres: dict[str, str] = field(default_factory=dict)
    api_key: str | None = None
    key_origin: str | None = None


@dataclass
class DiceEvent:
    """An event from either way in, normalized."""

    id: str
    name: str
    start: dt.datetime                 # Europe/London wall clock
    type_tags: list[str]
    genre_tags: list[str]
    status: str
    sold_out: bool
    price: str | None
    url: str
    description: str | None
    image_url: str | None


def http_client(headers: dict[str, str] | None = None) -> httpx.Client:
    return httpx.Client(
        headers=headers or {"User-Agent": CARTELITA_COMPAT_UA},
        follow_redirects=True,
        timeout=TIMEOUT,
    )


def local(iso: str, tz: str | None = None) -> dt.datetime:
    """An ISO timestamp (UTC "Z" or with an offset) → naive London wall clock."""
    when = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return when.astimezone(ZoneInfo(tz) if tz else LONDON).replace(tzinfo=None)


def price_from_pence(amounts: list[int | None]) -> str | None:
    """Ticket prices in pence → house convention (2x rule); all zero → free."""
    values = [a / 100 for a in amounts if a is not None]
    if not values:
        return None
    paid = [v for v in values if v > 0]
    if not paid:
        return "free"
    return format_gbp_range(min(paid), max(paid))


def event_url(raw: dict) -> str:
    """The event's readable dice.fm URL. The partner API gives `hash` and
    `perm_name` separately; an event page's `perm_name` already starts with
    the hash ("2w5mmm-cla-vincent-…")."""
    perm = raw.get("perm_name")
    if perm and raw.get("hash"):
        return f"{SITE}/event/{raw['hash']}-{perm}"
    if perm:
        return f"{SITE}/event/{perm}"
    return raw.get("url") or f"{SITE}/event/{raw['id']}"


# --- Key mode: the partner API -------------------------------------------------


def fetch_api(venue: Venue, http: httpx.Client) -> list[dict]:
    """Every upcoming event of `venue` (its own key, its own name filter).
    Pages by number on the partners host: the API's own `links.next` points at
    another host that refuses the key."""
    events: list[dict] = []
    for number in range(1, MAX_PAGES + 1):
        resp = http.get(
            API,
            params={"page[size]": PAGE_SIZE, "page[number]": number, "filter[venues][]": venue.dice_name},
            headers={"x-api-key": venue.api_key or ""},
        )
        resp.raise_for_status()
        payload = resp.json()
        events.extend(payload.get("data") or [])
        if not payload.get("data") or not (payload.get("links") or {}).get("next"):
            break
    return events


def from_api(raw: dict) -> DiceEvent:
    prices = [((t.get("price") or {}).get("total")) for t in raw.get("ticket_types") or []]
    images = raw.get("event_images") or {}
    return DiceEvent(
        id=raw["id"],
        name=raw["name"].strip(),
        start=local(raw["date"], raw.get("timezone")),
        type_tags=list(raw.get("type_tags") or []),
        genre_tags=list(raw.get("genre_tags") or []),
        status=raw.get("status") or "",
        sold_out=bool(raw.get("sold_out")),
        price=price_from_pence(prices),
        url=event_url(raw),
        description=(raw.get("raw_description") or raw.get("description") or "").strip() or None,
        image_url=images.get("landscape") or images.get("square") or next(iter(raw.get("images") or []), None),
    )


def api_events(venue: Venue, http: httpx.Client) -> list[DiceEvent]:
    """Key mode: only events at exactly this venue (the name filter is loose)."""
    return [
        from_api(raw) for raw in fetch_api(venue, http)
        if any(v.get("name") == venue.dice_name for v in raw.get("venues") or [])
    ]


# --- Public mode: venue page + event pages -------------------------------------


def next_data(html: str) -> dict:
    m = _NEXT_DATA.search(html)
    if not m:
        raise ValueError("no __NEXT_DATA__ on DICE page")
    return json.loads(m.group(1))


def venue_page_items(html: str) -> list[dict]:
    """The venue page's upcoming events (DICE shows the next 30)."""
    profile = next_data(html)["props"]["pageProps"].get("profile") or {}
    items: list[dict] = []
    for section in profile.get("sections") or []:
        for item in section.get("items") or []:
            if item.get("type") == "event" and item.get("event"):
                items.append(item["event"])
    return items


def event_page_details(html: str) -> dict:
    """An event page's own record (type tags, description, perm_name, hash)."""
    state = next_data(html)["props"]["pageProps"].get("initialState") or "{}"
    if isinstance(state, str):
        state = json.loads(state)
    return ((state.get("event") or {}).get("event")) or {}


def from_page(item: dict, details: dict) -> DiceEvent:
    dates = item.get("dates") or {}
    price = item.get("price") or {}
    amount = price.get("amount") if price.get("amount") is not None else price.get("amount_from")
    about = details.get("about") or {}
    status = item.get("status") or details.get("status") or ""
    return DiceEvent(
        id=item["id"],
        name=item["name"].strip(),
        start=local(dates["event_start_date"], dates.get("timezone")),
        type_tags=[t.get("value") for t in details.get("tags_types") or [] if t.get("value")],
        genre_tags=[],
        status=status,
        sold_out=status == "sold-out",
        price=price_from_pence([amount]),
        url=event_url({**details, "id": item["id"]}),
        description=(about.get("description") or "").strip() or None,
        image_url=(item.get("images") or {}).get("square"),
    )


def page_events(venue: Venue, http: httpx.Client) -> list[DiceEvent]:
    resp = http.get(f"{SITE}/venue/{venue.page}", headers=CARTELITA_BROWSER_HEADERS)
    resp.raise_for_status()
    items = [
        it for it in venue_page_items(resp.text)
        if any(v.get("name") == venue.dice_name for v in it.get("venues") or [])
    ]

    def details(item: dict) -> dict:
        page = http.get(f"{SITE}/event/{item['id']}", headers=CARTELITA_BROWSER_HEADERS)
        page.raise_for_status()
        return event_page_details(page.text)

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        return [from_page(it, d) for it, d in zip(items, pool.map(details, items))]


# --- Curation and output -------------------------------------------------------


def categorize(venue: Venue, event: DiceEvent) -> list[str]:
    """Our category for an event at `venue`, or [] when it isn't programme."""
    for tag in event.genre_tags:
        if tag in venue.genres:
            return [venue.genres[tag]]
    cats = [venue.types[t] for t in event.type_tags if t in venue.types]
    return list(dict.fromkeys(cats))


def genre_annotations(event: DiceEvent) -> list[str]:
    """"gig:post_punk" → "post punk" (DICE's genre tags, minus the prefix)."""
    out = [t.split(":", 1)[-1].replace("_", " ") for t in event.genre_tags]
    return list(dict.fromkeys(out))


def to_scraped(venue: Venue, events: list[DiceEvent]) -> list[ScrapedEvent]:
    out: list[ScrapedEvent] = []
    for ev in sorted(events, key=lambda e: e.start):
        if ev.status == "cancelled":
            continue
        cats = categorize(venue, ev)
        if not cats:
            continue
        out.append(
            ScrapedEvent(
                title=re.sub(r"\s+", " ", ev.name),
                start_date=ev.start.date(),
                start_time=ev.start.time(),
                source_url=ev.url,
                category_slugs=cats,
                price="sold-out" if ev.sold_out else ev.price,
                description=ev.description,
                image_url=ev.image_url,
                external_id=ev.id,
                annotations=genre_annotations(ev),
            )
        )
    return out


def scrape(venue: Venue) -> list[ScrapedEvent]:
    with http_client() as http:
        events = api_events(venue, http) if venue.api_key else page_events(venue, http)
    return to_scraped(venue, events)
