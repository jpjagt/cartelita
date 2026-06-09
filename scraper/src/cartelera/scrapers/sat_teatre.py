from __future__ import annotations

import datetime as dt
import re
import time

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.scrapers.price import format_eur_range
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# SAT! Sant Andreu Teatre (Sant Andreu, Barcelona) — family/kids theatre,
# contemporary dance, circus and music. Koobin-backed CMS in Catalan.
#
# Data is split across two layers (see sat_teatre_SOURCE.md):
#   1. The programacio list page lists every current/future SHOW (no pagination,
#      no date filter) as `.row[data-open-espectacle]` cards carrying the detail
#      URL, title, company and the genre tags used for categorisation. The card
#      shows only a date RANGE, NOT per-session dates.
#   2. Each show's detail page has a "Calendari i Sessions" rows view
#      (`#funcions .funcio`) with one element PER SESSION — session id, date+time
#      (from the session's Koobin buy link), and price.
# Strategy: discover show URLs + categories from the list, fetch each detail page
# once, and emit ONE ScrapedEvent per session (per occurrence).
PROGRAMACIO_URL = "https://www.sat-teatre.cat/ca/programacio.html"
BASE_URL = "https://www.sat-teatre.cat"
VENUE_SLUG = "sat-teatre"

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
_HTTPX_KWARGS: dict = dict(follow_redirects=True, timeout=30)

# Genre tag (from the list/detail `.cf .v` spans) -> our top-level category slug.
# A show may carry several tags and thus emit several slugs. "Festival Grec" and
# other festival labels are not genres -> captured as annotations, not categories.
_CAT_MAP: dict[str, str] = {
    "dansa": "dance",
    "contemporania": "dance",
    "urbana": "dance",
    "moviment": "dance",
    "familiar": "kids",
    "teatre": "theater",
    "circ": "theater",
    "titelles": "theater",
    "teatre visual": "theater",
    "clown": "theater",
    "teatre musical": "theater",
    "multidisciplinar": "theater",
    "tradicional": "theater",
    "musica": "pop",
    "classica": "classical",
    "flamenco": "flamenco",
}
_DEFAULT_CATEGORY = "theater"

_PRICE_NUM = re.compile(r"(\d+(?:[,\.]\d+)?)")
_FREE = re.compile(r"gratu\w*t|entrada\s+lliure", re.IGNORECASE)
_SOLD_OUT = re.compile(r"exhaurid|esgotat|sold[- ]?out", re.IGNORECASE)
# Local date+time embedded in a Koobin buy link: ...-YYYYMMDD-HHMM
_BUY_DT = re.compile(r"-(\d{8})-(\d{4})(?:\D|$)")
# UTC date+time in the Google-calendar fallback link: dates=YYYYMMDDTHHMMSS
_GCAL_DT = re.compile(r"dates=(\d{8})T(\d{6})")


def _strip_accents(text: str) -> str:
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _parse_price(raw: str | None) -> str | None:
    """Normalize a `.preu .valor` string ('12 EUR') to the Cartelera convention."""
    if not raw:
        return None
    txt = _clean(raw)
    if _FREE.search(txt):
        return "free"
    if _SOLD_OUT.search(txt):
        return "sold-out"
    nums = [float(n.replace(",", ".")) for n in _PRICE_NUM.findall(txt)]
    if not nums:
        return None
    lo, hi = round(min(nums)), round(max(nums))
    return format_eur_range(lo, hi)


def _map_categories(tags: list[str]) -> tuple[list[str], list[str]]:
    """Split genre tags into (category_slugs, annotations).

    Tags that map to a known slug become categories (deduped, order-preserved);
    unmapped tags (festival labels like 'Festival Grec') become annotations.
    """
    slugs: list[str] = []
    annotations: list[str] = []
    for tag in tags:
        clean = _clean(tag)
        if not clean:
            continue
        slug = _CAT_MAP.get(_strip_accents(clean).lower())
        if slug:
            if slug not in slugs:
                slugs.append(slug)
        else:
            annotations.append(clean)
    if not slugs:
        slugs = [_DEFAULT_CATEGORY]
    return slugs, annotations


def _extract_show_slug(url: str) -> str:
    """Return the show slug from a detail URL, e.g. '684-girafa'."""
    m = re.search(r"/p/c/([^/?#]+?)\.html", url)
    return m.group(1) if m else url


# -- List-page parser: show URL -> (categories, annotations, title) --------------

def parse_programacio(html: str) -> dict[str, dict]:
    """Parse the programacio list into a map: detail URL -> show metadata.

    Each entry: {title, company, category_slugs, annotations}. Per-session dates
    are NOT here -- they come from the detail page.
    """
    soup = BeautifulSoup(html, "html.parser")
    shows: dict[str, dict] = {}
    for card in soup.select(".row[data-open-espectacle]"):
        url = (card.get("data-open-espectacle") or "").strip()
        if not url:
            continue
        title_el = card.select_one(".titol")
        title = _clean(title_el.get_text(" ")) if title_el else ""
        company_el = card.select_one(".subtitol")
        company = _clean(company_el.get_text(" ")) if company_el else None
        tags = [v.get_text(" ") for v in card.select(".cf.op-multiple .v")]
        slugs, annotations = _map_categories(tags)
        shows[url] = {
            "title": title,
            "company": company,
            "category_slugs": slugs,
            "annotations": annotations,
        }
    return shows


# -- Detail-page parser: emit one ScrapedEvent per session -----------------------

def _session_datetime(funcio) -> tuple[dt.date, dt.time | None] | None:
    """Extract (date, time) for a session from its buy link (local) or gcal link."""
    buy = funcio.select_one("a.comprar")
    if buy:
        m = _BUY_DT.search(buy.get("href", ""))
        if m:
            date = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
            hhmm = m.group(2)
            t = dt.time(int(hhmm[:2]), int(hhmm[2:]))
            return date, (None if t == dt.time(0, 0) else t)
    # Fallback: Google-calendar link carries the UTC datetime; shift to Madrid.
    gcal = funcio.select_one("a[href*='google.com']")
    if gcal:
        m = _GCAL_DT.search(gcal.get("href", ""))
        if m:
            utc = dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
            # Europe/Madrid is UTC+2 in summer (DST), UTC+1 otherwise. Approximate
            # +2 for Apr-Oct, else +1.
            offset = 2 if 4 <= utc.month <= 10 else 1
            local = utc + dt.timedelta(hours=offset)
            return local.date(), local.time()
    return None


def parse_detail(html: str, show: dict, source_url: str) -> list[ScrapedEvent]:
    """Parse one show's detail page into one ScrapedEvent per session."""
    soup = BeautifulSoup(html, "html.parser")

    image_el = soup.select_one("meta[property='og:image']")
    image_url = image_el.get("content") if image_el else None

    h1 = soup.select_one("h1") or soup.select_one(".titol")
    title = show.get("title") or (_clean(h1.get_text(" ")) if h1 else "")
    company = show.get("company")
    category_slugs = show.get("category_slugs") or [_DEFAULT_CATEGORY]
    base_annotations = list(show.get("annotations") or [])
    if company:
        base_annotations = [company] + base_annotations

    show_slug = _extract_show_slug(source_url)

    events: list[ScrapedEvent] = []
    for funcio in soup.select("#funcions .funcio"):
        dttime = _session_datetime(funcio)
        if not dttime:
            continue
        start_date, start_time = dttime

        price_el = funcio.select_one(".preu .valor")
        price = _parse_price(price_el.get_text(" ") if price_el else None)

        # Session id from the `funcio-<id>` class -> stable per-occurrence key.
        funcio_id = None
        for cls in funcio.get("class", []):
            m = re.match(r"funcio-(\d+)", cls)
            if m:
                funcio_id = m.group(1)
                break
        if funcio_id:
            external_id = f"sat-{funcio_id}"
        else:
            time_str = start_time.strftime("%H%M") if start_time else "0000"
            external_id = f"{show_slug}@{start_date.isoformat()}T{time_str}"

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=source_url,
                category_slugs=list(category_slugs),
                price=price,
                image_url=image_url,
                external_id=external_id,
                annotations=list(base_annotations),
            )
        )
    return events


# -- Scraper class ---------------------------------------------------------------

class SatTeatreScraper:
    venue_slug = VENUE_SLUG

    def _get(self, url: str) -> str:
        for attempt in range(3):
            try:
                r = httpx.get(url, headers=_HEADERS, **_HTTPX_KWARGS)
                r.raise_for_status()
                return r.text
            except httpx.HTTPError:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("unreachable")

    def scrape(self) -> list[ScrapedEvent]:
        shows = parse_programacio(self._get(PROGRAMACIO_URL))
        if not shows:
            raise RuntimeError("No shows found on programacio page -- structure may have changed")

        events: list[ScrapedEvent] = []
        seen: set[str] = set()
        for url, show in shows.items():
            try:
                detail_html = self._get(url)
            except Exception:
                continue
            for ev in parse_detail(detail_html, show, url):
                if ev.external_id in seen:
                    continue
                seen.add(ev.external_id)
                events.append(ev)
        return events


register(
    scraper=SatTeatreScraper(),
    venue=VenueDefinition(
        slug="sat-teatre",
        name="SAT! Sant Andreu Teatre",
        city_slug="barcelona",
        address="C/ Neopàtria, 54, Sant Andreu",
        site_url="https://www.sat-teatre.cat/",
        category_slugs=["theater", "dance", "kids"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
