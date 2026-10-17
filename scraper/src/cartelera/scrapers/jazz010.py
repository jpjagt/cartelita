"""jazz010.live — the hand-curated Rotterdam jazz agenda (multi-venue source).

A WHITELIST source (like tomsarkgh): only the venues in `VENUES` are emitted;
venues owned by another source (BIRD, De Doelen, LantarenVenster, ...) and
venues outside Rotterdam are excluded on purpose. See jazz010_SOURCE.md for the
field map, the per-venue inclusion/exclusion rationale and the robots.txt
constraints (we fetch only `/events?start=...` and `/event/<slug>`).
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register_source
from cartelera.scrapers.http import CARTELITA_UA
from cartelera.types import (
    ListMembership,
    ScrapedEvent,
    SourceDefinition,
    VenueDefinition,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://jazz010.live"
SOURCE_SLUG = "jazz010"
USER_AGENT = CARTELITA_UA
TZ = ZoneInfo("Europe/Amsterdam")

# Pagination: each /events?start=D page covers 14 days and always links a
# VOLGENDE page, even far past the last event — so stop after this many empty
# pages in a row (12 weeks), with a hard cap as a safety net.
MAX_EMPTY_PAGES = 6
MAX_PAGES = 40
# robots.txt-friendly politeness: at most this many detail fetches in flight.
MAX_CONCURRENCY = 3

_MONTHS = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
}
# "wo 14 oktober 19:30" (time is sometimes missing: "wo 21 oktober").
_TIMESTAMP_RE = re.compile(
    r"^\s*\w+\s+(\d{1,2})\s+([a-z]+)(?:\s+(\d{1,2}):(\d{2}))?\s*$", re.IGNORECASE
)


def _key(name: str) -> str:
    return " ".join(name.split()).casefold()


def _venue(slug: str, name: str, address: str | None, site_url: str | None,
           lat: float | None = None, lng: float | None = None) -> VenueDefinition:
    return VenueDefinition(
        slug=slug,
        name=name,
        city_slug="rotterdam",
        address=address,
        site_url=site_url,
        lat=lat,
        lng=lng,
        category_slugs=["jazz"],
        list_memberships=[ListMembership(list_slug="jazz")],
    )


# The whitelist. Matched on the listing's location name (`.venue`), which is
# where the gig takes place — not the organiser shown on the detail page.
VENUES: list[VenueDefinition] = [
    _venue("vrijmoed", "Vrijmoed", "Ketelaarstraat 7, Rotterdam", "https://vrijmoedrotterdam.nl"),
    _venue("dizzy", "Dizzy", "'s-Gravendijkwal 127, Rotterdam", "https://dizzy.nl"),
    _venue("batavierhuis", "Batavierhuis", "Pieter de Hoochweg 108, Rotterdam", "https://batavierhuis.nl"),
    _venue("de-fruitvis", "De Fruitvis", "Marconistraat 43, Rotterdam", "https://jazzindefruitvis.nl"),
    _venue("grounds", "Grounds", "Pieter de Hoochweg 125, Rotterdam", "https://www.grounds.nu"),
    _venue("heerenhuys", "Heerenhuys", "Baden Powelllaan 12, Rotterdam", "https://hetparkinrotterdam.nl",
           51.90678, 4.46846),  # the pavilion in Het Park (OSM: "Dudok in Het Park")
    _venue("de-machinist", "De Machinist", "Willem Buytewechstraat 45, Rotterdam", None),
    _venue("het-witte-paard", "Het Witte Paard", "Groenezoom 245, Rotterdam", "https://hetwittepaardrotterdam.nl"),
    _venue("hillegondakerk", "Hillegondakerk", None, None),
    _venue("jazz-in-crooswijk", "Jazz in Crooswijk (Nivon)", "Dirk Smitsstraat 76, Rotterdam", None,
           51.92857, 4.48592),  # the Nivon house in Crooswijk (OSM)
]

# Location names as jazz010 spells them -> venue slug.
ALIASES: dict[str, str] = {
    _key(name): slug
    for name, slug in [
        ("Vrijmoed", "vrijmoed"),
        ("Dizzy", "dizzy"),
        ("Batavierhuis", "batavierhuis"),
        ("Jazz In De Fruitvis", "de-fruitvis"),
        ("De Fruitvis", "de-fruitvis"),
        ("Grounds", "grounds"),
        ("Heerenhuys", "heerenhuys"),
        ("De Machinist", "de-machinist"),
        ("Het Witte Paard", "het-witte-paard"),
        ("Hillegondakerk", "hillegondakerk"),
        ("Nivon", "jazz-in-crooswijk"),
    ]
}

# Location names deliberately left out (reasons in jazz010_SOURCE.md). Known
# so they're logged quietly; any OTHER unknown name is logged as a warning so a
# new venue on jazz010 gets an editorial look.
EXCLUDED: set[str] = {
    _key(n)
    for n in [
        # owned by another source (docs/nl-cities-plan.md)
        "LantarenVenster", "LantarenVenster Rotterdam", "de Doelen", "de Studio's",
        "BIRD", "Rotown", "Annabel", "WORM", "Baroeg", "Maassilo", "Toffler",
        "Roodkapje", "Poortgebouw", "Laurenskerk", "Luxor", "Theater Zuidplein",
        "KINO", "Cinerama", "Kantine Walhalla", "Mooi Weer", "Hofplein",
        "Maaspodium", "Dansateliers",
        # outside Rotterdam
        "Jazzland Café", "Westvestkerk", "Jazzpodium Hotspothutspot",
        "Vulcaan Vlaardingen",
        # curation: low-signal / not a jazz programme
        "Café LaBru", "Wilskracht Bar & Keuken", "De Buurvrouw",
        "Koffie & Ambacht", "De Zolder",
    ]
}


def venue_slug_for(name: str) -> str | None:
    return ALIASES.get(_key(name))


def _resolve_date(day: int, month: int, page_start: dt.date) -> dt.date:
    """The listing shows no year; it's the first (day, month) on/after the
    page's start date (a page never lists events before its start)."""
    candidate = dt.date(page_start.year, month, day)
    if candidate < page_start - dt.timedelta(days=7):
        candidate = dt.date(page_start.year + 1, month, day)
    return candidate


def parse_timestamp(text: str, page_start: dt.date) -> tuple[dt.date, dt.time | None] | None:
    m = _TIMESTAMP_RE.match(" ".join(text.split()))
    if not m:
        return None
    month = _MONTHS.get(m.group(2).lower())
    if not month:
        return None
    date = _resolve_date(int(m.group(1)), month, page_start)
    time = dt.time(int(m.group(3)), int(m.group(4))) if m.group(3) else None
    return date, time


def parse_listing_page(html: str, page_start: dt.date) -> tuple[list[dict], dt.date | None]:
    """One /events?start=D page -> (cards, start date of the VOLGENDE page).

    Only the main list counts: the `section.regional` "IN DE BUURT" block
    lists gigs outside Rotterdam (Den Haag, Dordrecht) and is skipped."""
    soup = BeautifulSoup(html, "html.parser")
    cards: list[dict] = []
    for art in soup.select("article.listing"):
        if art.find_parent(class_="regional"):
            continue
        ts = art.select_one(".timestamp")
        venue = art.select_one(".venue")
        link = art.select_one(".artist a")
        if not (ts and venue and link):
            continue
        parsed = parse_timestamp(ts.get_text(" ", strip=True), page_start)
        if parsed is None:
            logger.warning("jazz010: unparseable timestamp %r", ts.get_text(strip=True))
            continue
        href = link.get("href") or ""
        slug = href.rstrip("/").rsplit("/", 1)[-1] if href.startswith("/event/") else ""
        if slug == "event":
            slug = ""
        cards.append({
            "venue_name": " ".join(venue.get_text(" ", strip=True).split()),
            "title": link.get_text(" ", strip=True),
            "slug": slug,
            "start_date": parsed[0],
            "start_time": parsed[1],
            "free": art.select_one(".free-entrance") is not None,
            "sold_out": art.select_one(".sold-out") is not None,
            "tip": art.select_one(".tip") is not None,
        })
    next_start = None
    nxt = soup.select_one(".listing-footer a[href]")
    if nxt:
        m = re.search(r"start=(\d{4}-\d{2}-\d{2})", nxt["href"])
        if m:
            next_start = dt.date.fromisoformat(m.group(1))
    return cards, next_start


_AMOUNT_RE = re.compile(r"€\s*(\d+)(?:,(\d{2}|-{1,2}))?")


def parse_price(text: str | None) -> str | None:
    """'TICKETS - € 7,50' -> '7,50€'; '€ 45,--' -> '45€'; 'TICKETS -' -> None.
    Several amounts -> the highest."""
    if not text:
        return None
    best: tuple[float, str] | None = None
    for euros, cents in _AMOUNT_RE.findall(text):
        cents = cents if cents and cents.isdigit() and cents != "00" else ""
        value = int(euros) + (int(cents) / 100 if cents else 0)
        label = f"{int(euros)},{cents}€" if cents else f"{int(euros)}€"
        if best is None or value > best[0]:
            best = (value, label)
    return best[1] if best else None


def parse_detail(html: str) -> dict:
    """An /event/<slug> page -> organiser, ticket text, description, image."""
    soup = BeautifulSoup(html, "html.parser")
    header = soup.select_one(".event-header")
    organiser = " ".join(header.get_text(" ", strip=True).split()) if header else None
    ticket = None
    for btn in soup.select("a.button"):
        text = " ".join(btn.get_text(" ", strip=True).split())
        if text.upper().startswith("TICKETS"):
            ticket = text
            break
    parts: list[str] = []
    desc = soup.select_one(".event-description")
    if desc:
        paras = [p.get_text(" ", strip=True) for p in desc.find_all("p")]
        paras = [p for p in paras if p] or [desc.get_text(" ", strip=True)]
        parts.extend(p for p in paras if p)
    lineup = soup.select_one(".event-lineup")
    if lineup:
        members = []
        for a in lineup.select('a[href^="/performer/"]'):
            name = a.get_text(" ", strip=True)
            role = ""
            sib = a.next_sibling
            if isinstance(sib, str):
                role = sib.strip().lstrip("-").strip()
            members.append(f"{name} ({role})" if role else name)
        if members:
            parts.append("Bezetting: " + ", ".join(members))
    img = soup.select_one("img.event-photo")
    image_url = None
    if img and img.get("src"):
        src = img["src"]
        image_url = src if src.startswith("http") else BASE_URL + src
    return {
        "organiser": organiser,
        "ticket": ticket,
        "description": "\n\n".join(parts) or None,
        "image_url": image_url,
    }


def external_id(card: dict) -> str:
    # The slug embeds a date but is NOT reliable as one (copied entries keep a
    # stale date, one reads "...-invalid-datetime"), so qualify with the
    # listing's own date+time.
    t = card["start_time"].strftime("%H%M") if card["start_time"] else "none"
    return f"{card['slug']}@{card['start_date'].isoformat()}T{t}"


def build_event(card: dict, detail: dict | None) -> ScrapedEvent | None:
    venue_slug = venue_slug_for(card["venue_name"])
    if venue_slug is None or not card["slug"]:
        return None
    detail = detail or {}
    if card["sold_out"]:
        price = "sold-out"
    elif card["free"]:
        price = "free"
    else:
        price = parse_price(detail.get("ticket"))
    annotations: list[str] = []
    if card["tip"]:
        annotations.append("tip")
    organiser = detail.get("organiser")
    venue_names = {k for k, v in ALIASES.items() if v == venue_slug}
    if organiser and _key(organiser) not in venue_names:
        annotations.append(organiser)  # the series/organiser, e.g. "Cross Over Hillegonda"
    start_time = card["start_time"]
    return ScrapedEvent(
        title=card["title"],
        start_date=card["start_date"],
        start_time=start_time,
        start_times=[start_time] if start_time else [],
        source_url=f"{BASE_URL}/event/{card['slug']}",
        category_slugs=["jazz"],
        price=price,
        description=detail.get("description"),
        image_url=detail.get("image_url"),
        external_id=external_id(card),
        annotations=annotations,
        venue_slug=venue_slug,
    )


def select_cards(cards: list[dict]) -> list[dict]:
    """Dedup (consecutive pages overlap on their boundary day) and keep only
    whitelisted venues; log what's dropped."""
    seen: set[str] = set()
    kept: list[dict] = []
    unknown: set[str] = set()
    for card in cards:
        key = _key(card["venue_name"])
        if key not in ALIASES:
            if key not in EXCLUDED:
                unknown.add(card["venue_name"])
            continue
        if not card["slug"]:
            logger.warning("jazz010: %r at %s has no event link; skipped",
                           card["title"], card["venue_name"])
            continue
        eid = external_id(card)
        if eid in seen:
            continue
        seen.add(eid)
        kept.append(card)
    if unknown:
        logger.warning("jazz010: venues not in the whitelist (review): %s",
                       ", ".join(sorted(unknown)))
    return kept


class Jazz010Scraper:
    def _get(self, client: httpx.Client, url: str) -> str:
        resp = client.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text

    def scrape(self) -> list[ScrapedEvent]:
        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(headers=headers, follow_redirects=True) as client:
            cards: list[dict] = []
            start: dt.date | None = dt.datetime.now(TZ).date()
            empty = pages = 0
            while start and pages < MAX_PAGES and empty < MAX_EMPTY_PAGES:
                # A failing list page raises: partial data would read as misses.
                html = self._get(client, f"{BASE_URL}/events?start={start.isoformat()}")
                pages += 1
                page_cards, next_start = parse_listing_page(html, start)
                empty = 0 if page_cards else empty + 1
                cards.extend(page_cards)
                start = next_start if next_start and next_start > start else None
            if not cards:
                # The agenda always has gigs in the coming weeks; none at all
                # means the markup changed, not that Rotterdam went quiet.
                raise RuntimeError("jazz010: listing returned no events")

            kept = select_cards(cards)

            def fetch_detail(card: dict) -> dict | None:
                try:
                    return parse_detail(self._get(client, f"{BASE_URL}/event/{card['slug']}"))
                except httpx.HTTPError as exc:
                    logger.warning("jazz010: detail fetch failed for %s: %s", card["slug"], exc)
                    return None

            with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
                details = list(pool.map(fetch_detail, kept))
        if kept and all(d is None for d in details):
            raise RuntimeError(f"jazz010: all {len(kept)} detail fetches failed")
        events = [build_event(c, d) for c, d in zip(kept, details)]
        return [e for e in events if e is not None]


register_source(
    scraper=Jazz010Scraper(),
    source=SourceDefinition(slug=SOURCE_SLUG, name="jazz010.live", venues=VENUES),
)
