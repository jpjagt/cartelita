from __future__ import annotations

import datetime as dt
import re
import warnings
from functools import lru_cache

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers.price import format_eur_range
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Antic Teatre (Sant Pere, Barcelona) — independent experimental / multidisciplinary
# performing-arts space in a 1650 building. WordPress site; no usable event JSON-LD
# (only Yoast WebPage/BreadcrumbList boilerplate). Events data is split across two
# layers:
#   1. Monthly list pages (one per month, linked from the programacio nav) — each
#      .row card carries: day, time, category label, title, author, link to detail,
#      and an optional badge (.entry-extra: "estrena Barcelona", "Cicle mensual", …).
#   2. Individual event detail pages — price, full category, image_url live here.
# Strategy: discover month URLs from the programacio nav, parse all list rows, then
# fetch one detail page per unique show URL to enrich price/image, then combine into
# one ScrapedEvent per occurrence.
PROGRAMACIO_URL = "https://www.anticteatre.com/programacio/"
BASE_URL = "https://www.anticteatre.com"
VENUE_SLUG = "antic-teatre"

# SSL workaround: the site occasionally returns unexpected EOF on TLS negotiation.
# verify=False suppresses the error; warnings are silenced for cleaner output.
_HTTPX_KWARGS: dict = dict(follow_redirects=True, timeout=30, verify=False)
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# ── Catalan/Spanish month name → month number ──────────────────────────────────
_MONTH_MAP: dict[str, int] = {
    "gener": 1, "febrer": 2, "març": 3, "abril": 4,
    "maig": 5, "juny": 6, "juliol": 7, "agost": 8,
    "setembre": 9, "octubre": 10, "novembre": 11, "desembre": 12,
    # Spanish fallbacks
    "enero": 1, "febrero": 2, "marzo": 3, "mayo": 5,
    "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# Category labels from the site (both list-page and detail-page variants, after
# normalizing soft-hyphens and case) → our top-level category slugs.
# Antic Teatre is a theatre/performing-arts venue; everything maps to `theater`.
# "dance" covers explicitly dance-labelled works ("nous llenguatges del cos",
# "performance" can be either).
_CAT_MAP: dict[str, str] = {
    "performance": "theater",
    "noves dramatúrgies": "theater",
    "nous llenguatges del cos": "dance",
    "teatre": "theater",
    "circ": "theater",
    "arts escèniques comunitàries": "theater",
    "cabaret": "theater",
    "dansa": "dance",
    "dance": "dance",
    "theater": "theater",
}
_DEFAULT_CATEGORY = "theater"

# Price patterns
_EUR_NUM = re.compile(r"(\d+(?:[,\.]\d+)?)\s*euros?", re.IGNORECASE)
_FREE_MARKERS = re.compile(r"entrada\s+gratu[ïi]?ta|activitat\s+gratu[ïi]?ta|gratu[ïi]?t", re.IGNORECASE)
_SOLD_OUT = re.compile(r"\bsold[- ]?out\b|esgotat", re.IGNORECASE)

# Soft-hyphen character (U+00AD) and regular hyphens used in circle spans
_SOFT_HYPHEN = "­"


def _clean(text: str) -> str:
    """Normalize text from circle-span labels and other site elements.

    The site splits long labels across visual lines using two mechanisms:
    - soft-hyphen U+00AD followed by a space: 'lleng\xad uatjes del cos'
    - plain ASCII hyphen '-' followed by a newline/space: 'lleng- uatjes del cos'

    Both represent mid-word line breaks (not dashes). Remove them to reconstruct
    the original word, then collapse remaining whitespace.
    """
    # Remove soft-hyphen (U+00AD) + optional following space
    text = re.sub("­ ?", "", text)
    # Remove plain ASCII hyphen that acts as a line-break (followed by whitespace)
    text = re.sub(r"-\s+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_price(raw: str | None) -> str | None:
    """Normalize price text to the Cartelera convention.

    Patterns seen:
      '15 euros ONLINE // 17 euros TAQUILLA'  → 15, 17 → "17€" (hi < 2×lo)
      '8,5 euros ONLINE i 10 euros TAQUILLA'  → 8.5, 10 → "10€"
      'Entrada gratuïta'                       → "free"
      None / empty                             → None
    """
    if not raw:
        return None
    raw_stripped = raw.strip()
    if _FREE_MARKERS.search(raw_stripped):
        return "free"
    if _SOLD_OUT.search(raw_stripped):
        return "sold-out"
    nums_raw = _EUR_NUM.findall(raw_stripped)
    if not nums_raw:
        return None
    # Parse comma-decimal (Catalan) or dot-decimal (safe fallback)
    nums = [float(n.replace(",", ".")) for n in nums_raw]
    lo = min(nums)
    hi = max(nums)
    lo_int = round(lo)
    hi_int = round(hi)
    return format_eur_range(lo_int, hi_int)


def _normalize_category(raw: str | None) -> str:
    """Map a site category label to our slug, defaulting to 'theater'."""
    if not raw:
        return _DEFAULT_CATEGORY
    key = _clean(raw).lower()
    return _CAT_MAP.get(key, _DEFAULT_CATEGORY)


def _extract_slug(url: str) -> str | None:
    """Return the event slug from a detail URL, e.g. 'peti-suis-cia-supreema'."""
    m = re.search(r"/events/event/([^/?#]+)", url)
    return m.group(1) if m else None


def _parse_month_year(header_text: str) -> tuple[int, int] | None:
    """Parse 'Juny 2026' → (6, 2026), 'Setembre 2026' → (9, 2026)."""
    parts = header_text.strip().split()
    if len(parts) < 2:
        return None
    month_name = parts[0].lower()
    month = _MONTH_MAP.get(month_name)
    if not month:
        return None
    try:
        year = int(parts[1])
    except ValueError:
        return None
    return month, year


# ── Detail-page parser ─────────────────────────────────────────────────────────

def parse_detail(html: str) -> dict:
    """Extract price, category, and image_url from a single event detail page."""
    soup = BeautifulSoup(html, "html.parser")
    # Category circle: .entry-category .circle span (not .entry-extra)
    cat_circle = soup.select_one(".entry-category .circle span")
    raw_cat = _clean(cat_circle.text) if cat_circle else None
    category = _normalize_category(raw_cat)

    price_el = soup.select_one(".entry-price")
    # Strip the label prefix "Entrades: " before parsing
    price_raw = price_el.get_text(" ", strip=True) if price_el else None
    if price_raw:
        # Remove label prefix
        price_raw = re.sub(r"^Entrades?\s*:\s*", "", price_raw, flags=re.IGNORECASE).strip()
    price = _parse_price(price_raw)

    # Image: first wp-content/uploads img on the page (usually the event photo)
    image_url = None
    for img in soup.select("img"):
        src = img.get("src", "")
        if "wp-content/uploads" in src:
            image_url = src
            break

    return {"category": category, "price": price, "image_url": image_url}


# ── List-page parser ───────────────────────────────────────────────────────────

def parse_agenda(html: str, detail_cache: dict[str, dict] | None = None) -> list[ScrapedEvent]:
    """Parse one monthly Antic Teatre list page into ScrapedEvents.

    `detail_cache` maps event URL → {category, price, image_url} enrichments
    fetched from detail pages. When None (e.g. in offline fixture tests), the
    scraper falls back to the list-page category and leaves price/image as None.
    """
    soup = BeautifulSoup(html, "html.parser")

    header = soup.select_one("h2.archive-title")
    if not header:
        return []
    month_year = _parse_month_year(header.text)
    if not month_year:
        return []
    month, year = month_year

    events: list[ScrapedEvent] = []
    for row in soup.select(".row"):
        day_el = row.select_one(".entry-day-num")
        if not day_el:
            continue
        day_str = day_el.get_text(strip=True)
        try:
            day = int(day_str)
        except ValueError:
            continue

        # Time: "20:00" or a non-time string like "L'Antic al GREC 2026."
        time_el = row.select_one(".entry-time")
        time_raw = time_el.get_text(strip=True) if time_el else ""
        time_m = re.match(r"(\d{1,2}):(\d{2})", time_raw)
        start_time = dt.time(int(time_m.group(1)), int(time_m.group(2))) if time_m else None

        link_el = row.select_one(".entry-link")
        if not link_el:
            continue
        source_url = link_el.get("href", "").strip()
        if not source_url:
            continue

        title_el = row.select_one(".entry-title")
        title = _clean(title_el.get_text(" ")) if title_el else _clean(link_el.get("title", ""))
        if not title:
            continue

        author_el = row.select_one(".entry-author")
        author = _clean(author_el.get_text(" ")) if author_el else None

        # Category from list: often present and clean; fallback to detail enrichment
        cat_el = row.select_one(".entry-category.no-mobile")
        list_cat = _clean(cat_el.get_text(" ")) if cat_el else ""

        extra_el = row.select_one(".entry-extra")
        extra = _clean(extra_el.get_text(" ")) if extra_el else None

        try:
            start_date = dt.date(year, month, day)
        except ValueError:
            continue

        # Enrich from detail cache if available
        detail = (detail_cache or {}).get(source_url, {})
        category = detail.get("category") or _normalize_category(list_cat)
        price = detail.get("price")
        image_url = detail.get("image_url")

        # Annotations: author, site category label, extra badge, non-time venue note
        annotations: list[str] = []
        if author:
            annotations.append(author)
        list_cat_label = _clean(list_cat) if list_cat else (_clean(detail.get("raw_cat", "")) if detail else "")
        if list_cat_label:
            annotations.append(list_cat_label)
        if extra:
            annotations.append(extra)
        # Non-time entries in the time slot (e.g. "L'Antic al GREC 2026.")
        if time_raw and not time_m:
            annotations.append(time_raw)

        slug = _extract_slug(source_url)
        date_str = start_date.isoformat()
        time_str = start_time.strftime("%H%M") if start_time else "0000"
        external_id = f"{slug}@{date_str}T{time_str}" if slug else f"antic-teatre-{date_str}T{time_str}"

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=source_url,
                category_slugs=[category],
                price=price,
                image_url=image_url,
                external_id=external_id,
                annotations=annotations,
            )
        )
    return events


# ── Scraper class ──────────────────────────────────────────────────────────────

class AnticTeatreScraper:
    venue_slug = VENUE_SLUG

    def _get(self, url: str) -> str:
        warnings.filterwarnings("ignore", message=".*SSL.*")
        warnings.filterwarnings("ignore", category=UserWarning)
        r = httpx.get(url, headers=_HEADERS, **_HTTPX_KWARGS)
        r.raise_for_status()
        return r.text

    def _discover_month_urls(self) -> list[str]:
        """Return the current-programme monthly list-page URLs from the nav menu."""
        html = self._get(PROGRAMACIO_URL)
        soup = BeautifulSoup(html, "html.parser")
        urls = []
        for a in soup.select(".sub-menu a"):
            href = a.get("href", "")
            if (href.startswith(BASE_URL + "/programacio/")
                    and "4-mesos" in href
                    and href not in urls):
                urls.append(href)
        return urls

    def scrape(self) -> list[ScrapedEvent]:
        # 1. Discover monthly list pages
        month_urls = self._discover_month_urls()
        if not month_urls:
            raise RuntimeError("No monthly programme URLs found — site structure may have changed")

        # 2. Collect all list rows across months; gather unique detail URLs
        all_rows: list[tuple[str, str]] = []  # (month_html, month_url)
        detail_urls: set[str] = set()
        for url in month_urls:
            html = self._get(url)
            all_rows.append((html, url))
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.select(".entry-link"):
                href = link.get("href", "").strip()
                if href:
                    detail_urls.add(href)

        # 3. Fetch detail pages once per show (not per occurrence)
        detail_cache: dict[str, dict] = {}
        for url in detail_urls:
            try:
                detail_html = self._get(url)
                detail_cache[url] = parse_detail(detail_html)
            except Exception:
                # If a detail page fails, we still emit the event from list data
                pass

        # 4. Parse all list pages with the enriched detail cache
        events: list[ScrapedEvent] = []
        seen_ids: set[str] = set()
        for html, _url in all_rows:
            for ev in parse_agenda(html, detail_cache=detail_cache):
                if ev.external_id in seen_ids:
                    continue
                seen_ids.add(ev.external_id)
                events.append(ev)

        return events


register(
    scraper=AnticTeatreScraper(),
    venue=VenueDefinition(
        slug="antic-teatre",
        name="Antic Teatre",
        city_slug="barcelona",
        address="C/ de Verdaguer i Callís, 12, 08003 Barcelona",
        site_url="https://www.anticteatre.com",
        category_slugs=["theater", "dance"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
        ],
    ),
)
