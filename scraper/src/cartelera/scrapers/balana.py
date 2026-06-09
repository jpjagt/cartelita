from __future__ import annotations
import datetime as dt
import html as html_module
import json
import re
from typing import Iterator

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Grup Balañá operates three Barcelona theaters under one website:
# balanaenviu.com.  Shows are loaded via a POST endpoint that returns both a
# pre-rendered HTML blob and a structured JSON `shows` object.  Each show
# record in the JSON carries title, slug, genre, image, description and a
# single date range (start_date … end_date).  For shows spanning multiple
# sessions (start_date ≠ end_date) we fetch the individual event detail page
# which contains all concrete sessions (month/day/hour) in `.ticketsBox`.
#
# Price is not available anywhere on the site (listing, API, or detail pages).
# Every ScrapedEvent will have price=None.
#
# Paral·lel 62 (formerly BARTS) is NOT listed on balanaenviu.com — the site
# only covers Tívoli, Coliseum, and Borràs.  Its scraper is a registered stub
# that returns an empty list until an authoritative source is found.

BASE_URL = "https://www.balanaenviu.com"
API_URL = f"{BASE_URL}/webapi/shows-filter"
SHOW_URL_PREFIX = f"{BASE_URL}/espectaculo/"

# Internal theater IDs used by the API.
THEATER_ID_TIVOLI = "3"
THEATER_ID_COLISEUM = "2"
THEATER_ID_BORRAS = "4"

# Month abbreviations used in the ticketsBox sessions (Catalan).
_CA_MONTHS: dict[str, int] = {
    "GEN": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SET": 9, "OCT": 10, "NOV": 11, "DES": 12,
    # Spanish abbreviations sometimes appear too.
    "ENE": 1, "AGO": 8, "SEP": 9, "OCT": 10,
}

# Genre id → our category slug.
# Comèdia(5), Dansa(6), Monòlegs(7), Musical(9), Ponència(10), Infantil(11).
# The full variety we've seen across all three theaters; anything unrecognized
# defaults to "theater".
_GENRE_CATEGORY: dict[int, str] = {
    5: "theater",   # Comèdia
    6: "dance",     # Dansa
    7: "theater",   # Monòlegs
    9: "theater",   # Musical
    10: "theater",  # Ponència
    11: "kids",     # Infantil
}

_KNOWN_CATEGORIES = {"theater", "dance", "kids", "pop", "classical", "jazz", "film", "club", "flamenco"}

# Detect CANCEL·LAT / CANCELLED text in the venue's label.
_CANCELLED_RE = re.compile(r"cancel", re.IGNORECASE)
# Detect SOLD OUT / EXHAURIT.
_SOLDOUT_RE = re.compile(r"sold\s*out|exhaurit", re.IGNORECASE)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _make_session() -> httpx.Client:
    """Return an httpx Client with a fresh CSRF-seeded session cookie."""
    return httpx.Client(follow_redirects=True, timeout=30)


def _fetch_api(session: httpx.Client, theater_id: str, referer_url: str) -> dict:
    """GET the venue page (to seed cookies + CSRF), then POST shows-filter.
    Returns the parsed JSON dict: {shows: {data: [...]}, html: ..., hasMore: bool}.
    """
    page = session.get(referer_url)
    csrf_match = re.search(r'name="csrf-token"\s+content="([^"]+)"', page.text)
    csrf = csrf_match.group(1) if csrf_match else ""
    resp = session.post(
        API_URL,
        data={
            "_token": csrf,
            "theater": theater_id,
            "search": "",
            "startDate": "",
            "endDate": "",
            "page": 1,
            "section": "Theater",
        },
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Referer": referer_url,
            "X-CSRF-TOKEN": csrf,
        },
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Detail-page session parser
# ---------------------------------------------------------------------------

def _parse_sessions_from_detail_html(html: str) -> list[tuple[dt.date, dt.time | None, str | None]]:
    """Parse the `.ticketsBox__content--item` elements from a show detail page.

    Returns a list of (date, time, ticket_href) tuples.  `time` may be None if
    the hour element is missing.  `ticket_href` is the per-session buy URL (used
    to extract an occurrence-level id).
    """
    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[dt.date, dt.time | None, str | None]] = []
    year = dt.date.today().year

    for item in soup.select(".ticketsBox__content--item"):
        month_el = item.select_one('[class*="month"]')
        day_el = item.select_one('[class*="number"]')
        hour_el = item.select_one('[class*="hour"]')
        btn_el = item.select_one("a[href]")

        if not month_el or not day_el:
            continue
        month_str = month_el.get_text(strip=True).upper()[:3]
        month_num = _CA_MONTHS.get(month_str)
        if month_num is None:
            continue
        try:
            day = int(day_el.get_text(strip=True))
        except ValueError:
            continue

        # Infer year: if the month is earlier than today's month we assume next year.
        today = dt.date.today()
        candidate_year = today.year
        if month_num < today.month:
            candidate_year = today.year + 1
        try:
            date = dt.date(candidate_year, month_num, day)
        except ValueError:
            continue

        time: dt.time | None = None
        if hour_el:
            hour_text = hour_el.get_text(strip=True)
            m = re.match(r"(\d{1,2}):(\d{2})", hour_text)
            if m:
                try:
                    time = dt.time(int(m.group(1)), int(m.group(2)))
                except ValueError:
                    pass

        ticket_href = btn_el.get("href") if btn_el else None
        results.append((date, time, ticket_href))

    return results


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def _category_for_genre(genre: dict | None) -> str:
    """Map a genre dict (id, name.ca) to one of our category slugs."""
    if not genre:
        return "theater"
    genre_id = genre.get("id")
    return _GENRE_CATEGORY.get(genre_id, "theater")  # type: ignore[arg-type]


def _slug_for(show: dict) -> str:
    slug_obj = show.get("slug") or {}
    return slug_obj.get("ca") or slug_obj.get("es") or ""


def _title_for(show: dict) -> str:
    title_obj = show.get("title") or {}
    raw = title_obj.get("ca") or title_obj.get("es") or ""
    return html_module.unescape(raw).strip()


def _description_for(show: dict) -> str | None:
    desc_obj = show.get("description") or {}
    raw = desc_obj.get("ca") or desc_obj.get("es") or ""
    if not raw:
        return None
    # Strip HTML tags.
    text = re.sub(r"<[^>]+>", " ", html_module.unescape(raw))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _image_url_for(show: dict) -> str | None:
    thumb = show.get("thumbnail_image") or show.get("main_image")
    if not thumb:
        return None
    if thumb.startswith("http"):
        return thumb
    return f"https://pro-balana-laravel.s3.amazonaws.com/{thumb}"


def _detect_label(show_html_boxes: BeautifulSoup, slug: str) -> str | None:
    """Find the customLabel text (CANCEL·LAT, SOLD OUT) for a show slug in
    the listing HTML blob, if any."""
    link_el = show_html_boxes.select_one(f'a.box__image[href$="/{slug}"]')
    if not link_el:
        return None
    box = link_el.find_parent("div", class_="box")
    if not box:
        return None
    label_el = box.select_one(".customLabel")
    return label_el.get_text(strip=True) if label_el else None


def parse_shows(api_json: str, http_client: httpx.Client | None = None) -> list[ScrapedEvent]:
    """Parse the JSON response from /webapi/shows-filter into ScrapedEvents.

    Each show from the API carries a date range.  For shows with exactly one
    session (start == end or single day) we produce one event directly.  For
    multi-session shows we fetch the detail page (if http_client is provided)
    to get the individual occurrences; otherwise we fall back to a single event
    from the date range.
    """
    data = json.loads(api_json)
    shows = (data.get("shows") or {}).get("data") or []
    listing_html = data.get("html") or ""
    listing_soup = BeautifulSoup(listing_html, "html.parser")

    events: list[ScrapedEvent] = []

    for show in shows:
        slug = _slug_for(show)
        if not slug:
            continue
        title = _title_for(show)
        if not title:
            continue

        source_url = f"{SHOW_URL_PREFIX}{slug}"
        category = _category_for_genre(show.get("genre"))
        image_url = _image_url_for(show)
        description = _description_for(show)
        genre_name = ((show.get("genre") or {}).get("name") or {}).get("ca") or ""

        # Detect cancelled/sold-out from the listing HTML label.
        label_text = _detect_label(listing_soup, slug)
        if label_text and _CANCELLED_RE.search(label_text):
            # Skip cancelled shows entirely.
            continue
        price: str | None = None
        if label_text and _SOLDOUT_RE.search(label_text):
            price = "sold-out"

        annotations = [genre_name] if genre_name else []

        # Parse date range from API.
        start_dt_str = show.get("start_date") or ""
        end_dt_str = show.get("end_date") or ""
        start_api = _parse_api_datetime(start_dt_str)
        end_api = _parse_api_datetime(end_dt_str)

        if start_api is None:
            continue

        # Determine if we need to expand sessions.
        is_single = (
            end_api is None
            or end_api.date() == start_api.date()
        )

        if is_single:
            # Single occurrence.
            time = start_api.time() if start_api.time() != dt.time(0, 0) else None
            events.append(ScrapedEvent(
                title=title,
                start_date=start_api.date(),
                start_time=time,
                source_url=source_url,
                category_slugs=[category],
                price=price,
                description=description,
                image_url=image_url,
                external_id=_make_external_id(slug, start_api.date(), time),
                annotations=annotations,
            ))
        else:
            # Multi-session show: try to fetch the detail page.
            sessions: list[tuple[dt.date, dt.time | None, str | None]] = []
            if http_client is not None:
                try:
                    detail_resp = http_client.get(source_url)
                    sessions = _parse_sessions_from_detail_html(detail_resp.text)
                except Exception:
                    pass

            if sessions:
                for (sess_date, sess_time, _ticket_href) in sessions:
                    events.append(ScrapedEvent(
                        title=title,
                        start_date=sess_date,
                        start_time=sess_time,
                        source_url=source_url,
                        category_slugs=[category],
                        price=price,
                        description=description,
                        image_url=image_url,
                        external_id=_make_external_id(slug, sess_date, sess_time),
                        annotations=annotations,
                    ))
            else:
                # Fallback: one record for the range start.
                time = start_api.time() if start_api.time() != dt.time(0, 0) else None
                events.append(ScrapedEvent(
                    title=title,
                    start_date=start_api.date(),
                    start_time=time,
                    end_date=end_api.date() if end_api else None,
                    source_url=source_url,
                    category_slugs=[category],
                    price=price,
                    description=description,
                    image_url=image_url,
                    external_id=_make_external_id(slug, start_api.date(), time),
                    annotations=annotations,
                ))

    return events


def _parse_api_datetime(s: str) -> dt.datetime | None:
    """Parse '2026-06-12 20:00:00' → datetime, or None."""
    if not s:
        return None
    try:
        return dt.datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _make_external_id(slug: str, date: dt.date, time: dt.time | None) -> str:
    """Per-occurrence dedup key: slug@YYYY-MM-DDTHHMM."""
    hhmm = time.strftime("%H%M") if time else "0000"
    return f"balana-{slug}@{date.isoformat()}T{hhmm}"


# ---------------------------------------------------------------------------
# Base scraper class
# ---------------------------------------------------------------------------

class _BalanaScraper:
    """Shared implementation for all Balañá venue scrapers."""

    venue_slug: str
    _theater_id: str
    _page_url: str

    def scrape(self) -> list[ScrapedEvent]:
        with _make_session() as session:
            api_json = json.dumps(_fetch_api(session, self._theater_id, self._page_url))
            return parse_shows(api_json, http_client=session)


# ---------------------------------------------------------------------------
# Venue-specific scrapers
# ---------------------------------------------------------------------------

class TivoliScraper(_BalanaScraper):
    venue_slug = "teatre-tivoli"
    _theater_id = THEATER_ID_TIVOLI
    _page_url = f"{BASE_URL}/teatre/teatre-tivoli"


class ColiseumScraper(_BalanaScraper):
    venue_slug = "teatre-coliseum"
    _theater_id = THEATER_ID_COLISEUM
    _page_url = f"{BASE_URL}/teatre/teatre-coliseum"


class BorrasScraper(_BalanaScraper):
    venue_slug = "teatre-borras"
    _theater_id = THEATER_ID_BORRAS
    _page_url = f"{BASE_URL}/teatre/teatre-borras"


class Paralel62Scraper:
    """Stub scraper for Paral·lel 62 (formerly BARTS).

    As of 2026-06-09, Paral·lel 62 is not listed on balanaenviu.com — the site
    only covers Tívoli, Coliseum, and Borràs.  This scraper returns an empty
    list until an authoritative events source for the venue is identified.
    """
    venue_slug = "paralel-62"

    def scrape(self) -> list[ScrapedEvent]:
        return []


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

register(
    scraper=TivoliScraper(),
    venue=VenueDefinition(
        slug="teatre-tivoli",
        name="Teatre Tívoli",
        city_slug="barcelona",
        address="C/ de Casp, 8, 08010 Barcelona",
        site_url=BASE_URL,
        category_slugs=["theater", "dance", "kids"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)

register(
    scraper=ColiseumScraper(),
    venue=VenueDefinition(
        slug="teatre-coliseum",
        name="Teatre Coliseum",
        city_slug="barcelona",
        address="Gran Via de les Corts Catalanes, 595, 08007 Barcelona",
        site_url=BASE_URL,
        category_slugs=["theater", "dance", "kids"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)

register(
    scraper=BorrasScraper(),
    venue=VenueDefinition(
        slug="teatre-borras",
        name="Teatre Borràs",
        city_slug="barcelona",
        address="Plaça de Urquinaona, 9, 08010 Barcelona",
        site_url=BASE_URL,
        category_slugs=["theater", "dance", "kids"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)

register(
    scraper=Paralel62Scraper(),
    venue=VenueDefinition(
        slug="paralel-62",
        name="Paral·lel 62",
        city_slug="barcelona",
        address="Avinguda del Paral·lel, 62, 08001 Barcelona",
        site_url=BASE_URL,
        category_slugs=["theater", "dance", "kids", "pop"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
            ListMembership(list_slug="pop", whitelist_category_slug="pop"),
        ],
    ),
)
