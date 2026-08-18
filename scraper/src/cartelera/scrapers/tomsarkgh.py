from __future__ import annotations
import asyncio
import datetime as dt
import re

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register_source
from cartelera.types import (
    ScrapedEvent,
    VenueDefinition,
    ListMembership,
    SourceDefinition,
)

# tomsarkgh.am — Yerevan's main event-ticketing aggregator (~1,700+ events
# across ~1,900 venues, per-venue pages, English UI at /en/*). This is a
# MULTI-VENUE source: its `venues` list is the editorial whitelist (see
# tomsarkgh_SOURCE.md for the full field/category map and per-venue rationale).
BASE_URL = "https://www.tomsarkgh.am"
SOURCE_SLUG = "tomsarkgh"

# venue_slug -> (numeric tomsarkgh venue id, URL slug segment). The URL slug
# segment is cosmetic (the site resolves purely off the numeric id) but kept
# so the fetched URL matches what a human would see/click.
VENUE_IDS: dict[str, tuple[str, str]] = {
    "khachaturian-hall": ("20", "Aram-Khachaturyan-Concert-Hall.html"),
    "opera-ballet-theatre": ("18", "Armenian-National-Academic-Theatre-of-Opera-and-Ballet.html"),
    "sundukyan-theatre": ("8", "The-Gabriel-Sundukyan-State-Ac.html"),
    "hamazgayin-theatre": ("1", "Hamazgayin-State-Theater-named-afte.html"),
    "stanislavski-theatre": ("10", "Russian-drama-theatre-named-af.html"),
}

# Fixed display language per venue (the price-convention free-text field,
# never inferred from scraped text). Set per the editorial brief: Sundukyan
# and Hamazgayin perform in Armenian, Stanislavski in Russian (confirmed by
# recon: Stanislavski's own event descriptions on the site are themselves
# written in Russian, unlike the other two). Concert/opera/ballet venues have
# no single spoken language, so left unset.
LANGUAGE_BY_VENUE: dict[str, str | None] = {
    "khachaturian-hall": None,
    "opera-ballet-theatre": None,
    "sundukyan-theatre": "hy",
    "hamazgayin-theatre": "hy",
    "stanislavski-theatre": "ru",
}

# Theatrical genre labels tomsarkgh uses at the three drama theatres — all are
# staged plays, just genre-tagged (verified by inspecting titles: "Tale" ==
# Cinderella, "Comedy" == a stage comedy, "For kids" == a children's play).
_THEATER_TYPES = {"Theater", "Drama", "Tale", "Tragicomedy", "Comedy", "For kids"}

# Only the site's own event-type label ("Jazz", "Classical", "Opera & Ballet",
# ...) is used to categorize — never the title (see the skill's anti-pattern
# list). Returns None to mean "skip this event, no confident category slug".
def categorize(venue_slug: str, type_label: str | None) -> list[str] | None:
    if venue_slug == "khachaturian-hall":
        # The hall is a classical venue that also books mainstream/pop
        # programming (rooftop pop/rock/jazz/folk concerts, stand-up). Only
        # genuinely classical programming gets "classical"; everything else
        # collapses to "pop" (a seeded category with no Yerevan list yet, so
        # these correctly don't render anywhere — see SOURCE.md).
        return ["classical"] if type_label == "Classical" else ["pop"]
    if venue_slug == "opera-ballet-theatre":
        if type_label == "Opera":
            return ["classical"]
        if type_label == "Ballet":
            return ["dance"]
        if type_label == "Classical":
            return ["classical"]
        if type_label == "Dance":
            return ["dance"]
        if type_label == "Opera & Ballet":
            # A combined gala/production (e.g. an opera-house Giselle or
            # Sleeping Beauty listing) — genuinely both.
            return ["classical", "dance"]
        return None  # Jazz/Pop/Concert rentals: not opera/ballet/classical.
    if venue_slug in ("sundukyan-theatre", "hamazgayin-theatre", "stanislavski-theatre"):
        if type_label in _THEATER_TYPES:
            return ["theater"]
        return None  # Concert/Stand-up bookings unrelated to the venue's play programme.
    return None


def _abs_url(href: str | None) -> str | None:
    if not href:
        return None
    return href if href.startswith("http") else BASE_URL + href


def _event_id(href: str) -> str | None:
    m = re.search(r"/event/(\d+)/", href)
    return m.group(1) if m else None


def _venue_list_url(venue_slug: str) -> str:
    vid, slug = VENUE_IDS[venue_slug]
    return f"{BASE_URL}/en/venue/{vid}/{slug}"


def parse_venue_listing_page(html: str) -> tuple[list[dict], str | None]:
    """Parse one venue-listing HTML page (either the initial venue page or a
    'more' pagination fragment) into card dicts + the next pagination URL.

    Only cards carrying a `.event-venue` link are this venue's own upcoming
    events. Every venue page also embeds a site-wide "related events"
    carousel (other venues' events, no `.event-venue`) — the same trap noted
    in komitas_chamber_hall_SOURCE.md — which we must filter out or a
    whitelisted venue would appear to host, e.g., a Coca-Cola-sponsored
    concert or a stand-up night at the opera house.

    Deduped by event id within the page: the opera-ballet venue page was
    observed to render one event twice (once in a "featured" slot, once in
    the main list) — both copies carry `.event-venue`, so the carousel filter
    alone doesn't catch this; first occurrence wins.
    """
    soup = BeautifulSoup(html, "html.parser")
    cards: list[dict] = []
    seen_ids: set[str] = set()
    for box in soup.select("div.event-box-item"):
        if not box.select_one(".event-venue"):
            continue
        link = box.select_one("h4.event-title a") or box.select_one('a[href*="/en/event/"]')
        href = link.get("href") if link else None
        if not href:
            continue
        eid = _event_id(href)
        if not eid or eid in seen_ids:
            continue
        seen_ids.add(eid)
        type_el = box.select_one(".event-type")
        cards.append({
            "event_id": eid,
            "detail_url": _abs_url(href),
            "type_label": type_el.get_text(strip=True) if type_el else None,
        })
    more = soup.select_one("a.moreScope[href]")
    next_url = _abs_url(more.get("href")) if more else None
    return cards, next_url


_PRICE_TRIGGER_RE = re.compile(r"(Տոմս|Билет|Цена)")
# A "number" is either a run of digits grouped in triples by a thousands
# separator (space/comma/period — all three are used across the fixtures,
# e.g. "25.000", "4,000", "10 000") or a bare contiguous digit run. Matching
# the grouped form FIRST (before the bare-digits fallback) matters: without
# it, a comma-separated LIST of distinct prices ("25000, 30000") would be
# misread as thousands-grouping and collapse into one bogus giant number —
# a real bug caught during verification (see SOURCE.md).
_DIGIT_RUN_RE = re.compile(r"\d{1,3}(?:[ .,]\d{3})+|\d+")


def format_amd(lo: int, hi: int) -> str:
    """AMD price formatting, hand-rolled (not the euro helper — see the skill's
    price convention). Same 2x-spread rule: a single price when the spread is
    minor, a range only when the high tier is >= 2x the low."""
    if lo == hi or hi < 2 * lo:
        return f"{hi} AMD"
    return f"{lo}–{hi} AMD"


def parse_price(description_lines: list[str]) -> str | None:
    """Find the ticket-price line (Armenian "Տոմսերի արժեքը" / Russian "Цена
    билета"/"Билеты") among the description's lines and extract its digit
    runs (>=3 digits, to skip stray numbers like an age rating) as AMD price
    tiers. A trigger line with no usable digits (e.g. "tickets on sale, don't
    miss it" with no number) or no trigger line at all means unknown price —
    never guess from unrelated numbers elsewhere in the description (an age
    restriction, a running time)."""
    for line in description_lines:
        if not _PRICE_TRIGGER_RE.search(line):
            continue
        values = []
        for raw in _DIGIT_RUN_RE.findall(line):
            digits = re.sub(r"\D", "", raw)
            if len(digits) >= 3:
                values.append(int(digits))
        if values:
            return format_amd(min(values), max(values))
        return None  # trigger line present but no digits: price truly unstated
    return None


def parse_event_detail(html: str) -> dict | None:
    """Parse one event's detail page: title, start date/time, price,
    description, image, and the site's own event-type label. Returns None if
    the page carries no parseable start date (nothing reliable to emit)."""
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one("#eventName") or soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else None

    date_el = soup.select_one("[itemprop=startDate]")
    start_date = start_time = None
    if date_el and date_el.get("content"):
        try:
            parsed = dt.datetime.strptime(date_el["content"].strip(), "%Y-%m-%d %H:%M")
            start_date, start_time = parsed.date(), parsed.time()
        except ValueError:
            pass
    if not title or not start_date:
        return None

    type_el = soup.select_one(".scope-event-type")
    type_label = type_el.get_text(strip=True) if type_el else None

    desc_el = soup.select_one("#eventDesc")
    description = None
    price = None
    if desc_el:
        lines = [ln for ln in desc_el.get_text("\n", strip=True).split("\n") if ln]
        description = "\n".join(lines) or None
        price = parse_price(lines)

    img_el = soup.select_one("[itemprop=image]")
    image_url = _abs_url(img_el.get("src")) if img_el else None

    return {
        "title": title,
        "start_date": start_date,
        "start_time": start_time,
        "type_label": type_label,
        "description": description,
        "price": price,
        "image_url": image_url,
    }


def build_event(venue_slug: str, card: dict, detail: dict) -> ScrapedEvent | None:
    """Combine a listing card (event type discriminator) with its detail page
    (date/time/price/description) into a ScrapedEvent, or None if the event's
    type doesn't map to a seeded category for this venue (skip, never guess)."""
    # The detail page's own `.scope-event-type` is authoritative when present
    # (same principle as the skill's "prefer the detail page" guidance,
    # applied here because we fetch both anyway); the listing card's label is
    # only a fallback if the detail page is somehow missing it. Used for both
    # the category decision and the annotation so they never disagree.
    type_label = detail["type_label"] or card["type_label"]
    category_slugs = categorize(venue_slug, type_label)
    if not category_slugs:
        return None
    return ScrapedEvent(
        title=detail["title"],
        start_date=detail["start_date"],
        start_time=detail["start_time"],
        start_times=[detail["start_time"]] if detail["start_time"] else [],
        source_url=card["detail_url"],
        category_slugs=category_slugs,
        price=detail["price"],
        description=detail["description"],
        image_url=detail["image_url"],
        # Each tomsarkgh event id is already one occurrence (confirmed by
        # recon: a production running on consecutive nights gets one id per
        # night, e.g. ids 51418/51419 for the same title on 2026-11-26 and
        # -27) — no date qualification needed.
        external_id=f"tomsarkgh-{card['event_id']}",
        language=LANGUAGE_BY_VENUE.get(venue_slug),
        annotations=[type_label] if type_label else [],
        venue_slug=venue_slug,
    )


# Bound concurrent detail-page fetches: fast without hammering the site.
_MAX_CONCURRENCY = 8


async def _fetch(client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str) -> str | None:
    async with sem:
        try:
            resp = await client.get(url, follow_redirects=True, timeout=30)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError:
            return None


async def _scrape_venue(client: httpx.AsyncClient, sem: asyncio.Semaphore, venue_slug: str) -> list[ScrapedEvent]:
    # Paginate the venue's listing (the "more" link chain) synchronously via
    # the shared async client so it still shares the semaphore/connection pool.
    cards: list[dict] = []
    seen_ids: set[str] = set()
    url: str | None = _venue_list_url(venue_slug)
    hops = 0
    while url and hops < 20:
        html = await _fetch(client, sem, url)
        hops += 1
        if html is None:
            # Fail LOUDLY: a listing page that can't be fetched (site down,
            # network cut) must not read as "venue has no events" — an [ok] 0
            # would silently mask brokenness, while a raise marks the source
            # FAILED and leaves its existing rows untouched.
            raise RuntimeError(
                f"tomsarkgh: listing fetch failed for venue {venue_slug!r} ({url})"
            )
        page_cards, url = parse_venue_listing_page(html)
        for c in page_cards:
            if c["event_id"] not in seen_ids:
                seen_ids.add(c["event_id"])
                cards.append(c)

    details = await asyncio.gather(*(_fetch(client, sem, c["detail_url"]) for c in cards))
    # Individual detail pages may transiently fail (skipped below), but ALL of
    # them failing while the listing had cards is a network/site problem.
    if cards and all(h is None for h in details):
        raise RuntimeError(
            f"tomsarkgh: all {len(cards)} detail fetches failed for venue {venue_slug!r}"
        )

    events: list[ScrapedEvent] = []
    for card, html in zip(cards, details):
        if html is None:
            continue
        detail = parse_event_detail(html)
        if detail is None:
            continue
        event = build_event(venue_slug, card, detail)
        if event is not None:
            events.append(event)
    return events


async def _scrape_all(venue_slugs: list[str]) -> list[ScrapedEvent]:
    sem = asyncio.Semaphore(_MAX_CONCURRENCY)
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(_scrape_venue(client, sem, v) for v in venue_slugs))
    return [ev for venue_events in results for ev in venue_events]


class TomsarkghScraper:
    def scrape(self) -> list[ScrapedEvent]:
        return asyncio.run(_scrape_all(list(VENUE_IDS)))


register_source(
    scraper=TomsarkghScraper(),
    source=SourceDefinition(
        slug=SOURCE_SLUG,
        name="tomsarkgh.am",
        venues=[
            VenueDefinition(
                slug="khachaturian-hall",
                name="Aram Khachaturian Concert Hall",
                city_slug="yerevan",
                address="46 Mashtots street, Yerevan, Armenia",
                site_url="https://apo.am",
                category_slugs=["classical"],
                list_memberships=[
                    ListMembership(list_slug="classical", whitelist_category_slug="classical"),
                ],
            ),
            VenueDefinition(
                slug="opera-ballet-theatre",
                name="Armenian National Academic Theatre of Opera and Ballet",
                city_slug="yerevan",
                address="54 Tumanyan str., Yerevan, Armenia",
                site_url="https://www.opera.am",
                category_slugs=["classical", "dance"],
                list_memberships=[
                    ListMembership(list_slug="classical", whitelist_category_slug="classical"),
                    ListMembership(list_slug="dance", whitelist_category_slug="dance"),
                ],
            ),
            VenueDefinition(
                slug="sundukyan-theatre",
                name="Gabriel Sundukyan State Academic Theatre",
                city_slug="yerevan",
                address="6 Grigor Lusavorich str., Yerevan, Armenia",
                site_url="https://www.nationaltheater.am",
                category_slugs=["theater"],
                list_memberships=[ListMembership(list_slug="theater")],
            ),
            VenueDefinition(
                slug="hamazgayin-theatre",
                name="Hamazgayin State Theatre",
                city_slug="yerevan",
                address="3 Anri Vernoy St., Yerevan, Armenia",
                site_url="http://www.sostheatre.am",
                category_slugs=["theater"],
                list_memberships=[ListMembership(list_slug="theater")],
            ),
            VenueDefinition(
                slug="stanislavski-theatre",
                name="Stanislavski Russian Drama Theatre",
                city_slug="yerevan",
                address="7 Abovyan str., Yerevan, Armenia",
                category_slugs=["theater"],
                list_memberships=[ListMembership(list_slug="theater")],
            ),
        ],
    ),
)
