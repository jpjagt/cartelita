from __future__ import annotations
import asyncio
import datetime as dt
import html as html_module
import re

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# MEAM (Museu Europeu d'Art Modern, Barcelona) hosts weekly concert series in its
# Gomis Palace. The `/en/diary/` listing server-renders one `<li class="grid-item">`
# per upcoming concert occurrence, each carrying the title (with the series after a
# ` | ` separator), the detail URL, the full date + showtime, and an image — a
# single request is a near-complete source. Only the ticket price lives on the
# per-event detail page, so we enrich price from there (best-effort).
#
# The activities carousel (`/en/activities`) shows only a handful of items; the
# `/en/diary/` listing is authoritative (every occurrence in one page). See
# meam_SOURCE.md.
AGENDA_URL = "https://www.meam.es/en/diary/"
BASE_URL = "https://www.meam.es"
VENUE_SLUG = "meam"

_MAX_CONCURRENCY = 6

# The series — the venue's own programming discriminator, read from the title's
# ` | <series>` suffix (mirrored in the URL slug) — maps to our top-level category:
#   - "Saturday Classics" -> classical (chamber/classical recitals)
#   - "Friday Blues" / "Friday's Blues" -> jazz (closest existing; see SOURCE.md:
#     a dedicated `blues` category would be more truthful — recommended, not invented)
#   - "Sunday Sounds" -> jazz (intimate folk/contemporary acoustic — not classical)
# The series itself is also kept as a free-form annotation.
_SERIES_CATEGORY = {
    "saturday classics": "classical",
    "friday blues": "jazz",
    "friday's blues": "jazz",
    "sunday sounds": "jazz",
}
_DEFAULT_CATEGORY = "jazz"  # any future concert series defaults to the music bucket

# "Fri,  5 Jun 2026" / "Saturday, 6 Jun 2026" — weekday name, day, abbreviated
# month, year. The clock-icon line then carries "18:00".
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_DATE_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})")
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")

# English/Catalan/Spanish free-entry phrases to normalize to "free".
_FREE_PHRASES = (
    "free admission", "free entry", "entrada gratuïta", "activitat gratuïta",
    "entrada gratuita", "entrada libre", "gratis", "gratuït",
)
_SOLD_OUT_PHRASES = ("sold out", "sold-out", "exhausted", "esgotat", "agotad")
# A price line like "Advance ticket sales: 18.00€ / Price at the entrance: 18.00€".
_PRICE_AMOUNT_RE = re.compile(r"(\d+(?:[.,]\d{1,2})?)\s*€")


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").replace("\x96", "-").strip()


def _absolutize(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE_URL + url
    return url


def _split_title_series(raw_title: str) -> tuple[str, str | None]:
    """Split "Paul San Martin | Friday Blues" into (title, series)."""
    title = _clean(raw_title)
    if "|" in title:
        head, _, tail = title.rpartition("|")
        head, tail = head.strip(), tail.strip()
        if head and tail:
            return head, tail
    return title, None


def _category_for_series(series: str | None) -> str:
    if not series:
        return _DEFAULT_CATEGORY
    return _SERIES_CATEGORY.get(series.lower(), _DEFAULT_CATEGORY)


def _parse_meta_datetime(text: str) -> tuple[dt.date | None, dt.time | None]:
    """Parse "Fri,  5 Jun 2026 18:00" → (date, time)."""
    text = _clean(text)
    d = _DATE_RE.search(text)
    start_date: dt.date | None = None
    if d:
        day, mon, year = int(d.group(1)), d.group(2)[:3].lower(), int(d.group(3))
        month = _MONTHS.get(mon)
        if month:
            try:
                start_date = dt.date(year, month, day)
            except ValueError:
                start_date = None
    start_time: dt.time | None = None
    t = _TIME_RE.search(text)
    if t:
        hh, mm = int(t.group(1)), int(t.group(2))
        if 0 <= hh < 24 and 0 <= mm < 60:
            start_time = dt.time(hh, mm)
    return start_date, start_time


def normalize_price(text: str | None) -> str | None:
    """Normalize a free-text price line to the price convention.

    Returns "free" / "sold-out" / a concise "18€"-style string / None. When the
    line has multiple amounts (advance vs. door), use the highest public price."""
    if not text:
        return None
    low = text.lower()
    if any(p in low for p in _SOLD_OUT_PHRASES):
        return "sold-out"
    if any(p in low for p in _FREE_PHRASES):
        return "free"
    amounts = _PRICE_AMOUNT_RE.findall(text)
    if not amounts:
        return None
    values = [float(a.replace(",", ".")) for a in amounts]
    if all(v == 0 for v in values):
        return "free"
    top = max(values)
    # Drop a trailing ".00"; keep cents otherwise.
    rendered = f"{top:.2f}".rstrip("0").rstrip(".")
    return f"{rendered}€"


def parse_price(html: str) -> str | None:
    """Extract the ticket price from a MEAM detail page (the `h3.short` line)."""
    soup = BeautifulSoup(html, "html.parser")
    for h3 in soup.select("h3.short"):
        text = h3.get_text(" ", strip=True)
        if "€" in text or any(p in text.lower() for p in _FREE_PHRASES + _SOLD_OUT_PHRASES):
            return normalize_price(text)
    return None


def _external_id(source_url: str, start_date: dt.date | None, start_time: dt.time | None) -> str:
    """Per-OCCURRENCE dedup key. The detail id (e.g. 1415) is unique per concert
    occurrence here (each diary entry is a single dated session), but we qualify it
    with date+time anyway so the key stays per-occurrence-safe if the venue ever
    reuses ids across sessions."""
    m = re.search(r"/diary/(\d+)/", source_url)
    base = m.group(1) if m else source_url.rstrip("/").rsplit("/", 1)[-1]
    date_part = start_date.isoformat() if start_date else "0000-00-00"
    time_part = start_time.strftime("%H%M") if start_time else "0000"
    return f"{base}@{date_part}T{time_part}"


def parse_agenda(html: str) -> list[ScrapedEvent]:
    """Parse the MEAM `/en/diary/` listing into one ScrapedEvent per concert.

    One ScrapedEvent per `li.grid-item`: title (series stripped from the ` | `
    suffix) from `h3.short a`, detail URL from its href, date+time from the
    `.meta-data` line, image from the card thumb. Category is derived from the
    series (the venue's own discriminator); the series is also kept as an
    annotation. Price is not on the listing → enriched from the detail page in
    `scrape()`."""
    soup = BeautifulSoup(html, "html.parser")

    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for item in soup.select("ul.events-grid li.grid-item"):
        link = item.select_one("h3.short a")
        if not link:
            continue
        raw_title = link.get_text(" ", strip=True)
        href = link.get("href", "").strip()
        if not raw_title or not href:
            continue
        source_url = _absolutize(href)

        title, series = _split_title_series(raw_title)

        meta = item.select_one(".meta-data")
        meta_text = meta.get_text(" ", strip=True) if meta else ""
        start_date, start_time = _parse_meta_datetime(meta_text)
        if start_date is None:
            continue  # no reliable date; skip rather than guess

        external_id = _external_id(source_url, start_date, start_time)
        if external_id in seen:
            continue
        seen.add(external_id)

        img = item.select_one("img")
        image_url = _absolutize(img.get("src", "").strip()) if img and img.get("src") else None

        annotations: list[str] = []
        if series:
            annotations.append(series)

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=source_url,
                category_slugs=[_category_for_series(series)],
                price=None,  # enriched from the detail page in scrape()
                image_url=image_url,
                external_id=external_id,
                annotations=annotations,
            )
        )

    return events


async def _enrich_prices(events: list[ScrapedEvent]) -> None:
    """Fetch each event's detail page to fill in its ticket price (best-effort;
    network/parse failures leave price = None — the listing data is complete)."""
    sem = asyncio.Semaphore(_MAX_CONCURRENCY)

    async def fetch_one(event: ScrapedEvent, client: httpx.AsyncClient) -> None:
        async with sem:
            try:
                resp = await client.get(event.source_url, follow_redirects=True, timeout=30)
                resp.raise_for_status()
            except httpx.HTTPError:
                return
        event.price = parse_price(resp.text)

    async with httpx.AsyncClient() as client:
        await asyncio.gather(*(fetch_one(ev, client) for ev in events))


class MeamScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        html = httpx.get(AGENDA_URL, follow_redirects=True, timeout=30).text
        events = parse_agenda(html)
        asyncio.run(_enrich_prices(events))
        return events


register(
    scraper=MeamScraper(),
    venue=VenueDefinition(
        slug="meam",
        name="MEAM (Museu Europeu d'Art Modern)",
        city_slug="barcelona",
        address="Carrer de la Barra de Ferro, 5, Ciutat Vella, 08003 Barcelona",
        site_url="https://www.meam.es",
        # The venue runs a classical concert series and music (blues / folk) series;
        # it emits both categories. See SOURCE.md for the blues->jazz mapping and the
        # recommendation for a dedicated `blues` category.
        category_slugs=["classical", "jazz"],
        list_memberships=[
            ListMembership(list_slug="classical", whitelist_category_slug="classical"),
            ListMembership(list_slug="jazz", whitelist_category_slug="jazz"),
        ],
    ),
)
