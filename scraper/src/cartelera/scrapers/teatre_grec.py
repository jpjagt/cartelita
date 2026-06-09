from __future__ import annotations

import datetime as dt
import re

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.scrapers.price import format_eur_range
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Festival Grec de Barcelona — Barcelona's summer multidisciplinary performing-arts
# festival (June–Aug). Shows span theatre, dance, music, circus, performance, cinema
# and celebration, staged across many city venues (Teatre Grec, Teatre Lliure, Sala
# Beckett, …).
#
# Source: the "all shows" schedule, a Drupal-rendered list paginated by `?page=N`
# (N=0..5, ~18 cards/page, ~100+ events). No JSON-LD. Each list card carries title,
# detail URL, discipline (the category discriminator), author/company subtitle,
# space (venue), a free-form date range/list and an image — but NOT the price. Price
# lives only on each show's detail page, so we fetch one detail page per show.
#
# The site exposes no per-occurrence session list (only a textual date range like
# "From 17 June to 5 July" or "9 and 10 July"), so one ScrapedEvent == one SHOW
# (a run/season): start_date = earliest date in the string, end_date = latest. The
# external_id is the show slug (one row per show — no occurrence collapse).
# See teatre_grec_SOURCE.md.

BASE_URL = "https://www.barcelona.cat"
SCHEDULE_URL = "https://www.barcelona.cat/grec/en/menu/schedule"
NUM_PAGES = 6  # pages 0..5
VENUE_SLUG = "teatre-grec"
FESTIVAL_YEAR = 2026

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
_HTTPX_KWARGS: dict = dict(follow_redirects=True, timeout=30)

# Discipline label (from `.discipline-item`) -> our top-level category slug.
_CAT_MAP: dict[str, str] = {
    "theater": "theater",
    "theatre": "theater",
    "performance": "theater",
    "circus": "theater",
    "celebration": "theater",
    "dance": "dance",
    "music": "pop",      # generic live-music bucket; the site exposes no sub-genre
    "cinema": "film",
    "film": "film",
}
_DEFAULT_CATEGORY = "theater"

# English + Catalan + Spanish month names -> month number.
_MONTH_MAP: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    # Catalan
    "gener": 1, "febrer": 2, "març": 3, "abril": 4, "maig": 5, "juny": 6,
    "juliol": 7, "agost": 8, "setembre": 9, "octubre": 10, "novembre": 11, "desembre": 12,
    # Spanish
    "enero": 1, "febrero": 2, "marzo": 3, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "noviembre": 11, "diciembre": 12,
}
_MONTH_NAMES_RE = "|".join(sorted(_MONTH_MAP, key=len, reverse=True))

# Price parsing: the "€" sign marks the string as a price; once present, every
# number in it is a euro amount (handles "€26", "5 €", "€14-34", "From €10 to €22",
# "€12, €10 and €8"). A standalone number after a range dash carries no sign.
_HAS_EUR = re.compile(r"€")
_ANY_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_FREE_MARKERS = re.compile(r"\bfree\b|gratu[ïi]?t|entrada\s+lliure", re.IGNORECASE)
_SOLD_OUT = re.compile(r"sold[- ]?out|esgotat|s\.o\.", re.IGNORECASE)


def _abs_url(href: str) -> str:
    href = (href or "").strip()
    if href.startswith("http"):
        return href
    return BASE_URL + href if href.startswith("/") else href


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_category(discipline: str | None) -> str:
    if not discipline:
        return _DEFAULT_CATEGORY
    return _CAT_MAP.get(_clean(discipline).lower(), _DEFAULT_CATEGORY)


def _slug_from_url(url: str) -> str | None:
    m = re.search(r"/show/([^/?#]+)", url)
    return m.group(1) if m else None


def _parse_price(raw: str | None) -> str | None:
    """Normalize a Grec detail-page price string to the Cartelera convention.

    Examples: '€26' -> '26€'; '€14-34' -> '14–34€' (or '34€' if hi<2×lo);
    'From €10 to €22' -> via format_eur_range; '€21,50' -> '22€' (rounded);
    'Free with prior reservation' -> 'free'; 'Free entry (lecture) and €15
    (concert)' -> '15€' (a euro amount present means it's paid).
    """
    if not raw:
        return None
    raw = raw.strip()
    if _SOLD_OUT.search(raw):
        return "sold-out"
    if _HAS_EUR.search(raw):
        nums = [float(n.replace(",", ".")) for n in _ANY_NUM.findall(raw)]
        if nums:
            lo, hi = round(min(nums)), round(max(nums))
            return format_eur_range(lo, hi)
    if _FREE_MARKERS.search(raw):
        return "free"
    return None


# ── Date-string parsing ──────────────────────────────────────────────────────
# Strip parenthetical notes ("(English)") then walk the string left-to-right,
# tracking the "current month" (months are written after their day group, e.g.
# "25, 26, 30 June and 1, 2, 7, 8, 9 July"). Collect every (day, month) pair and
# take min as start, max as end. Also handles "From D MONTH to D MONTH",
# "From D to D MONTH", numeric "DD/MM", and month-first "July 9".

_PAREN = re.compile(r"\([^)]*\)")
_TOKEN = re.compile(r"(\d{1,2})/(\d{1,2})|(\d{1,2})|(" + _MONTH_NAMES_RE + r")", re.IGNORECASE)


def _parse_dates(raw: str, year: int = FESTIVAL_YEAR) -> tuple[dt.date | None, dt.date | None]:
    """Return (start_date, end_date) parsed from a free-form Grec date string.

    end_date is None for a single-date show. Returns (None, None) if unparseable.
    """
    if not raw:
        return None, None
    text = _PAREN.sub(" ", raw)

    # Walk tokens, assigning each bare day number to the *next* month name that
    # follows it (months trail their day group). Numeric DD/MM is self-contained.
    pending_days: list[int] = []
    pairs: list[tuple[int, int]] = []  # (month, day) for sortability
    for m in _TOKEN.finditer(text):
        dd, mm, day, month_name = m.groups()
        if dd and mm:  # DD/MM
            d, mo = int(dd), int(mm)
            if 1 <= mo <= 12 and 1 <= d <= 31:
                pairs.append((mo, d))
        elif day:
            pending_days.append(int(day))
        elif month_name:
            mo = _MONTH_MAP[month_name.lower()]
            for d in pending_days:
                if 1 <= d <= 31:
                    pairs.append((mo, d))
            pending_days = []
    # Month-first form ("July 9"): a month with days trailing it. Re-scan if no
    # pairs were formed but we have a month followed by day numbers.
    if not pairs:
        cur_month: int | None = None
        for m in _TOKEN.finditer(text):
            _dd, _mm, day, month_name = m.groups()
            if month_name:
                cur_month = _MONTH_MAP[month_name.lower()]
            elif day and cur_month:
                d = int(day)
                if 1 <= d <= 31:
                    pairs.append((cur_month, d))
    if not pairs:
        return None, None

    dates = sorted({dt.date(year, mo, d) for mo, d in pairs})
    start = dates[0]
    end = dates[-1] if len(dates) > 1 else None
    return start, end


# ── List-page parser ─────────────────────────────────────────────────────────

def parse_schedule(html: str, price_cache: dict[str, str | None] | None = None) -> list[ScrapedEvent]:
    """Parse one Grec schedule page into ScrapedEvents (one per show).

    `price_cache` maps source_url -> price string from the detail pages. When None
    (offline fixture tests) price is left as None.
    """
    soup = BeautifulSoup(html, "html.parser")
    events: list[ScrapedEvent] = []

    for card in soup.select(".node--type-activitat"):
        link = card.select_one("a.link-detail")
        if not link:
            continue
        source_url = _abs_url(link.get("href", ""))
        if not source_url:
            continue

        title_el = card.select_one(".title-activity")
        title = _clean(title_el.get_text()) if title_el else _clean(link.get_text())
        if not title:
            continue

        disc_el = card.select_one(".discipline-item")
        discipline = _clean(disc_el.get_text()) if disc_el else None
        category = _normalize_category(discipline)

        dates_el = card.select_one(".dates-activity")
        dates_raw = _clean(dates_el.get_text()) if dates_el else ""
        start_date, end_date = _parse_dates(dates_raw)
        if not start_date:
            continue

        # image: prefer data-src (lazyload), fall back to src
        img = card.select_one(".wrapper-img-activity img") or card.select_one("img")
        image_url = None
        if img:
            image_url = _abs_url(img.get("data-src") or img.get("src") or "")
            image_url = image_url or None

        # annotations: discipline label, author/company, venue space, raw date text
        annotations: list[str] = []
        if discipline:
            annotations.append(discipline)
        sub_el = card.select_one(".subtitle-activity")
        subtitle = _clean(sub_el.get_text()) if sub_el else None
        if subtitle:
            annotations.append(subtitle)
        space_el = card.select_one(".space-activity")
        if space_el:
            space = _clean(space_el.get_text())
            space = re.sub(r"\s*Space\s*$", "", space).strip()
            if space:
                annotations.append(space)
        if dates_raw:
            annotations.append(dates_raw)

        slug = _slug_from_url(source_url)
        external_id = f"{slug}@{start_date.isoformat()}" if slug else f"{VENUE_SLUG}-{title}@{start_date.isoformat()}"

        price = (price_cache or {}).get(source_url)

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                end_date=end_date,
                source_url=source_url,
                category_slugs=[category],
                price=price,
                image_url=image_url,
                external_id=external_id,
                annotations=annotations,
            )
        )
    return events


def parse_price_detail(html: str) -> str | None:
    """Extract the normalized price from one show detail page."""
    soup = BeautifulSoup(html, "html.parser")
    for label in soup.select(".label-content-activity"):
        if re.search(r"price|preu", label.get_text(), re.IGNORECASE):
            row = label.find_parent(class_="row")
            val = row.select_one(".col-7") if row else None
            if val:
                return _parse_price(_clean(val.get_text()))
    return None


# ── Scraper class ──────────────────────────────────────────────────────────────

class TeatreGrecScraper:
    venue_slug = VENUE_SLUG

    def _get(self, url: str) -> str:
        r = httpx.get(url, headers=_HEADERS, **_HTTPX_KWARGS)
        r.raise_for_status()
        return r.text

    def scrape(self) -> list[ScrapedEvent]:
        # 1. Fetch every schedule page (paginate — page 0 alone is only ~18 shows).
        page_htmls: list[str] = []
        for page in range(NUM_PAGES):
            url = f"{SCHEDULE_URL}?page={page}"
            html = self._get(url)
            page_htmls.append(html)
            # Stop early if a page has no cards (defensive against page-count drift).
            if not BeautifulSoup(html, "html.parser").select(".node--type-activitat"):
                break

        # 2. Collect unique detail URLs, fetch each once for price.
        detail_urls: list[str] = []
        seen_urls: set[str] = set()
        for html in page_htmls:
            for ev in parse_schedule(html):
                if ev.source_url not in seen_urls:
                    seen_urls.add(ev.source_url)
                    detail_urls.append(ev.source_url)

        price_cache: dict[str, str | None] = {}
        for url in detail_urls:
            try:
                price_cache[url] = parse_price_detail(self._get(url))
            except Exception:
                price_cache[url] = None

        # 3. Parse all pages with price enrichment; dedup by external_id.
        events: list[ScrapedEvent] = []
        seen_ids: set[str] = set()
        for html in page_htmls:
            for ev in parse_schedule(html, price_cache=price_cache):
                if ev.external_id in seen_ids:
                    continue
                seen_ids.add(ev.external_id)
                events.append(ev)
        return events


register(
    scraper=TeatreGrecScraper(),
    venue=VenueDefinition(
        slug="teatre-grec",
        name="Teatre Grec",
        city_slug="barcelona",
        address="Passeig de Santa Madrona, Montjuïc, 08038 Barcelona",
        site_url="https://www.barcelona.cat/grec/en",
        category_slugs=["theater", "dance", "pop", "film"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
            ListMembership(list_slug="pop", whitelist_category_slug="pop"),
            ListMembership(list_slug="film", whitelist_category_slug="film"),
        ],
    ),
)
