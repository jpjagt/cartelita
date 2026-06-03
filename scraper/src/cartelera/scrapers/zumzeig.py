from __future__ import annotations
import datetime as dt
import html as html_module
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Zumzeig Cinecooperativa (Sants, Barcelona) — an independent cooperative arthouse
# cinema. Its `/cinema/calendari/` page server-renders a month-grid table per
# upcoming month, with one `<a class="sessio">` per screening occurrence inside a
# `<td class="day" rel="YYYY-MM-DD">` cell. That cell carries the ISO date and the
# anchor carries the local showtime, title, film id and cycle — a single request
# is a complete source (no per-film detail fetch). See zumzeig_SOURCE.md.
#
# We use the calendar rather than the `/cinema/sessions/` ("Cartellera") list,
# because that list groups by film and truncates a film's sessions with a `+`
# marker, so it does NOT list every occurrence — the calendar does.
AGENDA_URL = "https://zumzeigcine.coop/cinema/calendari/"
BASE_URL = "https://zumzeigcine.coop"
VENUE_SLUG = "zumzeig"

_HOUR = re.compile(r"(\d{1,2}):(\d{2})")

# Catalan free-entry phrases to normalize to "free" if a price ever surfaces on the
# calendar/detail. None are present today (the site exposes no scrape-able price),
# but the upsert/repair flow benefits from the rule being recorded here.
_FREE_PHRASES = ("entrada gratuïta", "activitat gratuïta", "entrada lliure", "gratis")


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").strip()


def _absolutize(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE_URL + url
    return url


def _normalize_price(text: str | None) -> str | None:
    """Normalize a free-text price; today Zumzeig exposes none → None.

    Kept so the repair flow has a single place to map Catalan free-entry phrases."""
    if not text:
        return None
    low = text.lower()
    if any(p in low for p in _FREE_PHRASES):
        return "free"
    return _clean(text) or None


def _sessio_date(sessio: Tag) -> dt.date | None:
    """Occurrence date from the parent `td.day[rel]` ISO attribute."""
    cell = sessio.find_parent("td")
    raw = cell.get("rel", "") if cell else ""
    try:
        return dt.date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def _sessio_time(sessio: Tag) -> tuple[dt.time | None, bool]:
    """Local showtime from `.hora`, plus whether it's an accompanied screening.

    `.hora` is like `"18:30"` or `"18:30*"` — the trailing `*` (also rendered as a
    separate `span.acompanyat`) marks a guest/colloquium screening."""
    el = sessio.select_one(".hora")
    raw = el.get_text(strip=True) if el else ""
    accompanied = "*" in raw or sessio.select_one(".acompanyat") is not None
    m = _HOUR.search(raw)
    if not m:
        return None, accompanied
    hh, mm = int(m.group(1)), int(m.group(2))
    if 0 <= hh < 24 and 0 <= mm < 60:
        return dt.time(hh, mm), accompanied
    return None, accompanied


def parse_agenda(html: str) -> list[ScrapedEvent]:
    """Parse the Zumzeig calendar page into one ScrapedEvent per screening.

    One ScrapedEvent per `a.sessio`: title from `.film`, detail URL from `href`,
    local showtime from `.hora`, date from the parent `td.day[rel]`. Every session
    is category `film` (the `tipo` attribute is a programming cycle, captured as an
    annotation, not a top-level category). The film id is qualified by the
    occurrence's date+time for the per-occurrence `external_id`."""
    soup = BeautifulSoup(html, "html.parser")

    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for sessio in soup.select("a.sessio"):
        title_el = sessio.select_one(".film")
        title = _clean(title_el.get_text(" ", strip=True)) if title_el else ""
        href = sessio.get("href", "").strip()
        if not title or not href:
            continue

        start_date = _sessio_date(sessio)
        if start_date is None:
            continue  # no reliable date; skip rather than guess

        start_time, accompanied = _sessio_time(sessio)
        source_url = _absolutize(href.split("?")[0].rstrip("/") + "/")

        # external_id must be unique per OCCURRENCE, not per film: the same film
        # (e.g. "Corredora") screens on several dates and the upsert dedups on
        # (venue, external_id). The `filmid`/slug is shared across screenings, so
        # qualify it with the date+time.
        film_id = sessio.get("filmid") or source_url.rstrip("/").rsplit("/", 1)[-1]
        time_part = start_time.strftime("%H%M") if start_time else "0000"
        external_id = f"{film_id}@{start_date.isoformat()}T{time_part}"

        # Dedup within the batch: the raw page repeats month tables, so the same
        # occurrence can appear more than once.
        if external_id in seen:
            continue
        seen.add(external_id)

        annotations: list[str] = []
        cycle = sessio.get("tipo")
        if cycle:
            annotations.append(_clean(cycle).title())
        if accompanied:
            annotations.append("acompanyat")

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=source_url,
                category_slugs=["film"],
                price=None,  # site exposes no scrape-able ticket price
                external_id=external_id,
                annotations=annotations,
            )
        )

    return events


class ZumzeigScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            html = client.get(AGENDA_URL).text
        return parse_agenda(html)


register(
    scraper=ZumzeigScraper(),
    venue=VenueDefinition(
        slug="zumzeig",
        name="Zumzeig Cinecooperativa",
        city_slug="barcelona",
        address="Carrer de Béjar, 53, Sants-Montjuïc, 08014 Barcelona",
        site_url="https://zumzeigcine.coop",
        category_slugs=["film"],
        list_memberships=[
            ListMembership(list_slug="film"),
        ],
    ),
)
