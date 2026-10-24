"""Royal Ballet and Opera — the Royal Opera House, Covent Garden (main stage
and the Linbury Theatre).

rbo.org.uk is a React app that server-renders its data: the listing
`/tickets-and-events` embeds `window.__REACT_QUERY_DEHYDRATED_STATE__`, whose
`eventsPage` query holds every event (`performances[] {date,
performanceType}`, `locations`, `tags`) plus the tag and location names. One
page carries all of them (`?page=N` returns the same JSON). Curation, all on
the site's own labels (see royal_opera_house_SOURCE.md):

- production pages only (`sourceType` single-production-page; not the
  cinema-season `?mode=cinema` cards);
- tag "Opera and music" → classical, "Ballet and dance" → dance; an event
  also tagged Tours / Rehearsals / Talks and insights / Workshops and
  activities is dropped;
- at the Main Stage or the Linbury Theatre (other rooms — Clore Studio,
  Crush Room, foyers, Thurrock, online, cinemas — are dropped);
- public performances only: `performanceType` standard or relaxed (schools
  matinees, Young RBO, Paul Hamlyn Club, Friends rehearsals are not on
  general sale).

Price: each kept production's own page (`productionPageUrl`, one request
each) embeds its performances (`stage-activity`: id, date) and their live
availability (`activityAvailability`: min/max available price, tickets
left) — "£47–273"; no tickets left → "sold-out".
"""

from __future__ import annotations

import datetime as dt
import html
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.scrapers.price import format_gbp_range
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

logger = logging.getLogger(__name__)

VENUE_SLUG = "royal-opera-house"
SITE = "https://www.rbo.org.uk"
LISTING_URL = f"{SITE}/tickets-and-events"
LONDON = ZoneInfo("Europe/London")

GENRE_TAGS = {"Opera and music": "classical", "Ballet and dance": "dance"}
EXCLUDED_TAGS = {"Tours", "Rehearsals", "Talks and insights", "Workshops and activities"}
STAGES = {"Main Stage", "Linbury Theatre"}
PUBLIC_PERFORMANCES = {"standard", "relaxed"}
MAX_CONCURRENCY = 3

_STATE = re.compile(r"window\.__REACT_QUERY_DEHYDRATED_STATE__\s*=\s*")


def dehydrated_state(page: str) -> dict:
    m = _STATE.search(page)
    if not m:
        raise ValueError("rbo.org.uk: no __REACT_QUERY_DEHYDRATED_STATE__ on the page")
    state, _end = json.JSONDecoder().raw_decode(page[m.end():])
    return state


def events_page(page: str) -> dict:
    """The listing's `eventsPage` data: {events, tags, locations, …}."""
    for query in dehydrated_state(page)["queries"]:
        if query.get("queryKey", [None])[0] == "eventsPage":
            return query["state"]["data"]["events"]
    raise ValueError("rbo.org.uk: no eventsPage query in the listing")


def categorize(event: dict, tag_names: dict[str, str], location_names: dict[str, str]) -> list[str]:
    """Our categories for a listing event; [] drops it."""
    if event.get("sourceType") != "single-production-page" or event.get("isCancelled"):
        return []
    if event.get("isHiddenFromTicketsAndEvents"):
        return []
    page = event.get("productionPageUrl") or ""
    if not page.startswith("/production/") or "mode=cinema" in page:
        return []
    tags = {tag_names.get(t, "") for t in event.get("tags") or []}
    if tags & EXCLUDED_TAGS:
        return []
    if not {location_names.get(loc, "") for loc in event.get("locations") or []} & STAGES:
        return []
    return [cat for tag, cat in GENRE_TAGS.items() if tag in tags]


def _text(fragment: str | None) -> str | None:
    text = re.sub(r"<[^>]+>", " ", fragment or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text or None


def _start(iso: str) -> dt.datetime:
    return dt.datetime.fromisoformat(iso).astimezone(LONDON).replace(tzinfo=None)


def production_prices(page: str) -> dict[dt.datetime, str]:
    """A production page → its performances' prices, keyed by start
    (Europe/London wall clock): the available min/max price, or "sold-out"
    when no tickets are left."""
    starts: dict[str, dt.datetime] = {}
    avail: dict[str, dict] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            kind, attrs = node.get("type"), node.get("attributes")
            if kind == "stage-activity" and isinstance(attrs, dict) and attrs.get("date"):
                starts[str(node.get("id"))] = _start(attrs["date"])
            elif kind == "activityAvailability" and isinstance(attrs, dict) and attrs:
                avail[str(node.get("id"))] = attrs
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(dehydrated_state(page))
    out: dict[dt.datetime, str] = {}
    for activity_id, start in starts.items():
        a = avail.get(activity_id)
        if not a:
            continue
        if a.get("ticketsAvailable") == 0:
            out[start] = "sold-out"
        elif a.get("minPriceAvailable") is not None and a.get("maxPriceAvailable") is not None:
            out[start] = format_gbp_range(float(a["minPriceAvailable"]), float(a["maxPriceAvailable"]))
    return out


def parse(
    listing: str,
    prices: dict[str, dict[dt.datetime, str]] | None = None,
    today: dt.date | None = None,
) -> list[ScrapedEvent]:
    """The listing page → one ScrapedEvent per upcoming public performance
    of a kept production. `prices`: production page path →
    production_prices()."""
    today = today or dt.date.today()
    data = events_page(listing)
    tag_names = {t["id"]: t["title"].strip() for t in data.get("tags") or []}
    location_names = {loc["id"]: loc["title"].strip() for loc in data.get("locations") or []}
    prices = prices or {}
    out: list[ScrapedEvent] = []
    for event in data.get("events") or []:
        cats = categorize(event, tag_names, location_names)
        if not cats:
            continue
        page = event["productionPageUrl"]
        image = (event.get("imageResult") or {}).get("desktopPath")
        for perf in event.get("performances") or []:
            if perf.get("performanceType") not in PUBLIC_PERFORMANCES:
                continue
            start = _start(perf["date"])
            if start.date() < today:
                continue
            out.append(ScrapedEvent(
                title=_text(event["title"]) or event["title"],
                start_date=start.date(),
                start_time=start.time(),
                source_url=SITE + page,
                category_slugs=list(cats),
                price=prices.get(page, {}).get(start),
                description=_text(event.get("description")),
                image_url=image or None,
                external_id=f"{event['id']}@{start.isoformat(timespec='minutes')}",
                annotations=["relaxed performance"] if perf["performanceType"] == "relaxed" else [],
            ))
    return sorted(out, key=lambda e: (e.start_date, e.start_time))


def kept_production_pages(listing: str) -> list[str]:
    data = events_page(listing)
    tag_names = {t["id"]: t["title"].strip() for t in data.get("tags") or []}
    location_names = {loc["id"]: loc["title"].strip() for loc in data.get("locations") or []}
    pages = [e["productionPageUrl"] for e in data.get("events") or [] if categorize(e, tag_names, location_names)]
    return list(dict.fromkeys(pages))


def fetch_prices(pages: list[str]) -> dict[str, dict[dt.datetime, str]]:
    """Production page path → its prices; a page that fails just leaves
    that production's prices unknown."""

    def one(page: str) -> tuple[str, dict[dt.datetime, str]]:
        try:
            return page, production_prices(fetch(SITE + page, headers=CARTELITA_BROWSER_HEADERS))
        except Exception as exc:  # a price is optional, never a failed run
            logger.warning("rbo.org.uk: no prices from %s (%s)", page, exc)
            return page, {}

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        return dict(pool.map(one, pages))


class RoyalOperaHouseScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        listing = fetch(LISTING_URL, headers=CARTELITA_BROWSER_HEADERS)
        return parse(listing, fetch_prices(kept_production_pages(listing)))


register(
    scraper=RoyalOperaHouseScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Royal Opera House",
        city_slug="london",
        address="Bow Street, London WC2E 9DD",
        site_url=SITE,
        instagram_url="https://www.instagram.com/royalballetandopera",
        category_slugs=["classical", "dance"],
        list_memberships=[
            ListMembership(list_slug="classical", whitelist_category_slug="classical"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
        ],
    ),
)
