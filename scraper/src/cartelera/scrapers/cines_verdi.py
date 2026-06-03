from __future__ import annotations
import datetime as dt
import html as html_module
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Cines Verdi Barcelona is an independent arthouse cinema with two screens (Verdi
# + Verdi Park) served from one subdomain. The canonical homepage
# (www.cines-verdi.com) is just a Barcelona/Madrid chooser; the real site is the
# `barcelona.` subdomain. Every request 403s without a browser-like User-Agent.
#
# The /cartelera page server-renders one <article> per film, but the showtimes
# are lazy-loaded via JS: each article's `loadMovieData(imdbid, slug)` calls
# `/api/get-event-by-imdbid/<imdbid>`, whose JSON carries every screening
# (date, time, hall, price). So we parse the HTML for film stubs (imdbid, slug,
# title, poster), then fetch that JSON API per film and emit one ScrapedEvent per
# performance. See cines_verdi_SOURCE.md.
BASE_URL = "https://barcelona.cines-verdi.com"
CARTELERA_URL = f"{BASE_URL}/cartelera"
API_TMPL = f"{BASE_URL}/api/get-event-by-imdbid/{{imdbid}}"
VENUE_SLUG = "cines-verdi"

# The site rejects requests without a browser UA (403). httpx's default UA trips it.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_LOAD_MOVIE = re.compile(r"loadMovieData\('([^']+)','([^']*)'\)")


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").strip()


def _absolutize(url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE_URL + url
    # bare relative path (some Verdi slugs lack the leading slash, e.g.
    # "sessio-teta-el-drama") — resolve against the site root.
    return f"{BASE_URL}/{url}"


def _format_price(prices: list[str] | None) -> str | None:
    """Max public price from the cents strings, Spanish-formatted.

    The API gives `data.tickets.prices` as integer-cents strings (e.g. "600",
    "750"). We take the highest (the standard adult fare, skipping discount tiers)
    and render it as "7,50€", or "6€" when round."""
    cents: list[int] = []
    for p in prices or []:
        try:
            cents.append(int(p))
        except (TypeError, ValueError):
            continue
    if not cents:
        return None
    top = max(cents)
    euros, rem = divmod(top, 100)
    return f"{euros}€" if rem == 0 else f"{euros},{rem:02d}€"


class FilmStub:
    """A film as listed on /cartelera: the API key + display content."""

    __slots__ = ("imdbid", "slug", "title", "image_url", "source_url")

    def __init__(self, imdbid: str, slug: str, title: str | None, image_url: str | None):
        self.imdbid = imdbid
        self.slug = slug
        self.title = title
        self.image_url = image_url
        self.source_url = _absolutize(slug) if slug else BASE_URL


def parse_cartelera(html: str) -> list[FilmStub]:
    """Parse the /cartelera HTML into film stubs (imdbid, slug, title, poster).

    One stub per `<article>` carrying `loadMovieData('<imdbid>','<slug>')`. The
    showtimes are NOT in this HTML (lazy-loaded) — `scrape()` fetches them per
    stub from the JSON API."""
    soup = BeautifulSoup(html, "html.parser")
    stubs: list[FilmStub] = []
    seen: set[str] = set()
    for art in soup.find_all("article"):
        attrs = " ".join(str(v) for v in art.attrs.values())
        m = _LOAD_MOVIE.search(html_module.unescape(attrs))
        if not m:
            continue
        imdbid, slug = m.group(1), m.group(2)
        if imdbid in seen:
            continue
        seen.add(imdbid)

        title_el = art.select_one(".info-cartelera-performances header h2") or art.select_one("h2")
        title = _clean(title_el.get_text(strip=True)) if title_el else None

        img = art.select_one(".aside figure img[src]") or art.select_one("img[src]")
        image_url = _absolutize(img.get("src", "")) if img and img.get("src") else None

        stubs.append(FilmStub(imdbid, slug, title or None, image_url))
    return stubs


def _parse_perf_datetime(perf: dict) -> tuple[dt.date | None, dt.time | None]:
    """`schedule_date` "YYYYMMDD" + `time` "YYYYMMDDhhmmss" → local date/time."""
    date = None
    sd = str(perf.get("schedule_date") or "")
    if len(sd) == 8 and sd.isdigit():
        try:
            date = dt.date(int(sd[0:4]), int(sd[4:6]), int(sd[6:8]))
        except ValueError:
            date = None
    time = None
    tm = str(perf.get("time") or "")
    if len(tm) >= 12 and tm[:12].isdigit():
        hh, mm = int(tm[8:10]), int(tm[10:12])
        if 0 <= hh < 24 and 0 <= mm < 60:
            time = dt.time(hh, mm)
        if date is None:  # fall back to the date embedded in `time`
            try:
                date = dt.date(int(tm[0:4]), int(tm[4:6]), int(tm[6:8]))
            except ValueError:
                pass
    return date, time


def parse_film_events(stub: FilmStub, api_json: dict) -> list[ScrapedEvent]:
    """One ScrapedEvent per performance in the film's API JSON.

    `result.events` is a list of versions (language/projection variants); each
    has a `performances` list — one performance = one screening occurrence. The
    `performance.id` is globally unique, so it is the per-occurrence external_id."""
    result = (api_json or {}).get("result") or {}
    title = stub.title or _clean(str(result.get("name") or "")) or None
    if not title:
        return []

    events: list[ScrapedEvent] = []
    for version in result.get("events") or []:
        language = _clean(str(version.get("language") or ""))
        for perf in version.get("performances") or []:
            start_date, start_time = _parse_perf_datetime(perf)
            if start_date is None:
                continue

            prices = ((perf.get("data") or {}).get("tickets") or {}).get("prices")
            hall = _clean(str(perf.get("hall_name") or ""))
            annotations = [a for a in (hall, language) if a]

            perf_id = perf.get("id")
            external_id = str(perf_id) if perf_id is not None else None

            events.append(
                ScrapedEvent(
                    title=title,
                    start_date=start_date,
                    start_time=start_time,
                    source_url=stub.source_url,
                    category_slugs=["film"],
                    price=_format_price(prices),
                    image_url=stub.image_url,
                    external_id=external_id,
                    annotations=annotations,
                )
            )
    return events


class CinesVerdiScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        seen_ids: set[str] = set()
        with httpx.Client(follow_redirects=True, timeout=30, headers=_HEADERS) as client:
            stubs = parse_cartelera(client.get(CARTELERA_URL).text)
            for stub in stubs:
                try:
                    api_json = client.get(API_TMPL.format(imdbid=stub.imdbid)).json()
                except (httpx.HTTPError, ValueError):
                    continue
                for ev in parse_film_events(stub, api_json):
                    # Guard against the same performance appearing under two stubs.
                    if ev.external_id is not None:
                        if ev.external_id in seen_ids:
                            continue
                        seen_ids.add(ev.external_id)
                    events.append(ev)
        return events


register(
    scraper=CinesVerdiScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Cines Verdi",
        city_slug="barcelona",
        address="Carrer de Verdi, 32, Gràcia, 08012 Barcelona",
        site_url="https://barcelona.cines-verdi.com",
        category_slugs=["film"],
        list_memberships=[
            ListMembership(list_slug="film"),
        ],
    ),
)
