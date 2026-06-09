"""Mercat de les Flors (Barcelona) — "Casa de la Dansa"

Dance and movement-theater venue. All programming is dance-centric; elPetit
events (children's programme) are tagged kids in addition to dance.

Data source: WordPress AJAX endpoint (carregar_directori action) returns
rendered HTML cards for the current season. Each card links to a detail page
(/espectacle/<slug>/ or /activitat/<slug>/) where prices and per-occurrence
dates live in .esp-det-lft/.esp-det-rgt label/value pairs, with a .dte-lst
for per-occurrence Patronbase links when tickets are live.

List URL: https://mercatflors.cat/temporada-a-la-vista/
AJAX URL: https://mercatflors.cat/wp-admin/admin-ajax.php
  action=carregar_directori, meta_query[1][key]=temporada_vista, value=1,
  tax_query[0][taxonomy]=temporada, terms=[8776]

Category mapping:
  - "dance" for all events (the venue is "Casa de la Dansa")
  - "kids" added for elPetit events (title contains "elPetit" or "elPetit"
    appears in URL) and school matinees ("funcions escolars" in title)
    — school matinees are technically closed to the public but are listed
    publicly; we include them with kids + dance categories.

External ID: <espectacle-slug>@<YYYY-MM-DD>T<HHMM>  (per-occurrence)
  When .dte-lst is present, use the Patronbase perf_id:
    <patronbase_prod_id>_<patronbase_perf_id>
  Otherwise: <url-slug>@<YYYY-MM-DD>T<HHMM> (from parsed date + horari)

Price:
  "Tarifa" field from detail page → .desk-para text (take highest public price).
  "DIVENDRES JOVE" and other discount/accessibility tiers are ignored.
  "Gratuït" / "0 €" / "Activitat gratuïta" → "free".
  "Exhaurit" / "Esgotat" / "Sold Out" → "sold-out".

Verified: 2026-06-09
"""
from __future__ import annotations

import datetime as dt
import re
import urllib.parse

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers.price import format_eur_range
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

AJAX_URL = "https://mercatflors.cat/wp-admin/admin-ajax.php"
LIST_URL = "https://mercatflors.cat/temporada-a-la-vista/"
BASE_URL = "https://mercatflors.cat"
VENUE_SLUG = "mercat-flors"

# Catalan month names → month number
_CA_MONTHS = {
    "gener": 1, "febrer": 2, "març": 3, "abril": 4,
    "maig": 5, "juny": 6, "juliol": 7, "agost": 8,
    "setembre": 9, "octubre": 10, "novembre": 11, "desembre": 12,
}

# Abbreviated Catalan months (in .dte-lst: "13 juny", "15 oct")
_CA_MONTHS_ABBR = {
    "gen": 1, "feb": 2, "mar": 3, "abr": 4,
    "mai": 5, "jun": 6, "jul": 7, "ago": 8,
    "set": 9, "oct": 10, "nov": 11, "des": 12,
}

# Time formats: "20:00h", "20.30h", "20.30 h", "20 h", "12 h i 17 h" → take first
# Group 1+2: HH:MM h or HH.MM h (with optional space before h)
# Group 3: HH h (standalone)
_TIME_RE = re.compile(r"\b(\d{1,2})[:.](\d{2})\s*h|\b(\d{1,2})\s*h\b", re.IGNORECASE)
_PRICE_EUR = re.compile(r"(\d+(?:[.,]\d{2})?)\s*€")
_FREE_RE = re.compile(r"gratu[ïi]", re.IGNORECASE)
_SOLD_OUT_RE = re.compile(r"exhaurit|esgotat|sold.?out", re.IGNORECASE)

# DTE-LST date format: "Dissabte, 13 juny (20:00h)"
_DTE_DATE_RE = re.compile(
    r"(\d{1,2})\s+([a-zàáâäèéêëìíîïòóôöùúûü]+)\s*\((\d{1,2}):(\d{2})h\)",
    re.IGNORECASE,
)

# Text date patterns
_SINGLE_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+d[e']?\s*([a-zàáâäèéêëìíîïòóôöùúûü]+)\b",
    re.IGNORECASE,
)
# "Del 3 al 5 d'octubre" or "Del 2 al 5 i 11 i 12 d'octubre"
# Captures: start_day, [more stuff], month_name
# Month name is the LAST Catalan word in the string
_RANGE_START_RE = re.compile(
    r"del\s+(\d{1,2})\s+al\s+(\d{1,2})",
    re.IGNORECASE,
)
# Month name at end: "d'octubre", "de novembre"
_MONTH_AT_END_RE = re.compile(
    r"d[e']?\s*([a-zàáâäèéêëìíîïòóôöùúûü]+)\s*$",
    re.IGNORECASE,
)
# "31 d'octubre i 1 de novembre" — cross-month pair
_CROSS_MONTH_RE = re.compile(
    r"(\d{1,2})\s+d[e']?\s*([a-zàáâäèéêëìíîïòóôöùúûü]+)\s+i\s+(\d{1,2})\s+d[e']?\s*([a-zàáâäèéêëìíîïòóôöùúûü]+)",
    re.IGNORECASE,
)


def _resolve_month(name: str) -> int | None:
    n = name.lower().strip()
    m = _CA_MONTHS.get(n)
    if m:
        return m
    # Try abbreviated
    for abbr, num in _CA_MONTHS_ABBR.items():
        if n.startswith(abbr):
            return num
    return None


def _guess_year(month: int) -> int:
    """Guess the year for a month number, assuming near-future events."""
    today = dt.date.today()
    # If month is in the past relative to today's month, it's next year
    if month < today.month:
        return today.year + 1
    return today.year


def _parse_dte_item(text: str) -> tuple[dt.date, dt.time] | None:
    """Parse a .dte-lst item like 'Dissabte, 13 juny (20:00h)'."""
    m = _DTE_DATE_RE.search(text)
    if not m:
        return None
    day = int(m.group(1))
    month_name = m.group(2)
    hour = int(m.group(3))
    minute = int(m.group(4))
    month = _resolve_month(month_name)
    if not month:
        return None
    year = _guess_year(month)
    try:
        date = dt.date(year, month, day)
        time = dt.time(hour, minute)
        return date, time
    except ValueError:
        return None


def _parse_text_dates(text: str) -> list[dt.date]:
    """Parse a Catalan date text into a list of dates.

    Handles:
    - "13 de juny"
    - "Del 2 al 5 i 11 i 12 d'octubre"  (range + extra days, same month)
    - "Del 3 al 5 d'octubre"             (simple range)
    - "Del 6 al 10 d'octubre"            (simple range)
    - "17 i 18 d'octubre"                (two days, same month)
    - "31 d'octubre i 1 de novembre"     (cross-month pair)
    - "28 de setembre"                   (single date)
    """
    text = text.strip()
    if not text:
        return []

    # Cross-month pair: "31 d'octubre i 1 de novembre"
    # Only applies when "del" is NOT present (avoids false match in range strings)
    cross_m = _CROSS_MONTH_RE.search(text)
    if cross_m and "del" not in text.lower():
        day1, mname1 = int(cross_m.group(1)), cross_m.group(2)
        day2, mname2 = int(cross_m.group(3)), cross_m.group(4)
        month1 = _resolve_month(mname1)
        month2 = _resolve_month(mname2)
        if month1 and month2:
            y1 = _guess_year(month1)
            y2 = _guess_year(month2)
            dates = []
            try:
                dates.append(dt.date(y1, month1, day1))
            except ValueError:
                pass
            try:
                dates.append(dt.date(y2, month2, day2))
            except ValueError:
                pass
            if dates:
                return dates

    # Range-based: "Del 2 al 5 d'octubre" or "Del 2 al 5 i 11 i 12 d'octubre"
    range_m = _RANGE_START_RE.search(text)
    if range_m:
        start_day = int(range_m.group(1))
        end_day = int(range_m.group(2))
        # Month is at the end of the string
        month_m = _MONTH_AT_END_RE.search(text)
        if not month_m:
            # Try finding the last month-like word
            all_months = re.findall(
                r"d[e']?\s*([a-zàáâäèéêëìíîïòóôöùúûü]+)", text, re.IGNORECASE
            )
            month_name = all_months[-1] if all_months else None
        else:
            month_name = month_m.group(1)
        if month_name:
            month = _resolve_month(month_name)
            if month:
                year = _guess_year(month)
                dates = []
                # Generate all days in the range
                for d in range(start_day, end_day + 1):
                    try:
                        dates.append(dt.date(year, month, d))
                    except ValueError:
                        pass
                # Collect any additional days after "al end_day" (e.g. "i 11 i 12")
                # Look for standalone day numbers in the text after the range match
                rest = text[range_m.end():]
                for extra_m in re.finditer(r"\b(\d{1,2})\b", rest):
                    extra_day = int(extra_m.group(1))
                    if 1 <= extra_day <= 31:
                        try:
                            extra_date = dt.date(year, month, extra_day)
                            if extra_date not in dates:
                                dates.append(extra_date)
                        except ValueError:
                            pass
                return sorted(dates)

    # Same-month list: "17 i 18 d'octubre", "1 i 2 de novembre"
    same_month_m = re.search(
        r"(\d{1,2})\s+i\s+(\d{1,2})\s+d[e']?\s*([a-zàáâäèéêëìíîïòóôöùúûü]+)",
        text, re.IGNORECASE
    )
    if same_month_m:
        day1 = int(same_month_m.group(1))
        day2 = int(same_month_m.group(2))
        month = _resolve_month(same_month_m.group(3))
        if month:
            year = _guess_year(month)
            dates = []
            for d in [day1, day2]:
                try:
                    dates.append(dt.date(year, month, d))
                except ValueError:
                    pass
            return dates

    # Single date: "13 de juny", "28 de setembre", "9 d'octubre"
    single_m = _SINGLE_DATE_RE.search(text)
    if single_m:
        day = int(single_m.group(1))
        month = _resolve_month(single_m.group(2))
        if month:
            year = _guess_year(month)
            try:
                return [dt.date(year, month, day)]
            except ValueError:
                pass

    return []


def _parse_time(horari: str | None) -> dt.time | None:
    """Extract the first time from a horari string like '20 h', '20.30 h', '20:30h'."""
    if not horari:
        return None
    m = _TIME_RE.search(horari)
    if not m:
        return None
    if m.group(1) is not None:  # HH:MM or HH.MM format
        h, mn = int(m.group(1)), int(m.group(2))
    else:  # HH h format
        h, mn = int(m.group(3)), 0
    if h > 23 or mn > 59:
        return None
    return dt.time(h, mn)


def _parse_price(tarifa: str | None) -> str | None:
    """Parse price from Tarifa field text.

    Handles:
    - "8 €" → "8€"
    - "22 €" → "22€"
    - "Gratuït" → "free"
    - "0 €" → "free"
    - "Exhaurit" → "sold-out"
    - "30 €" → "30€"
    """
    if not tarifa:
        return None
    t = tarifa.strip()
    if _SOLD_OUT_RE.search(t):
        return "sold-out"
    if _FREE_RE.search(t):
        return "free"
    prices = [int(float(m.group(1).replace(",", "."))) for m in _PRICE_EUR.finditer(t)]
    if not prices:
        return None
    # Filter out 0 (accessibility tier)
    public_prices = [p for p in prices if p > 0]
    if not public_prices:
        return "free"
    lo = min(public_prices)
    hi = max(public_prices)
    return format_eur_range(lo, hi)


def _get_detail_fields(soup: BeautifulSoup) -> dict[str, str]:
    """Extract label→value pairs from .esp-det-lft / .esp-det-rgt."""
    fields: dict[str, str] = {}
    lft = soup.select(".esp-det-lft")
    rgt = soup.select(".esp-det-rgt")
    for label_el, value_el in zip(lft, rgt):
        label = label_el.get_text(strip=True).upper()
        value = value_el.get_text(" ", strip=True)
        fields[label] = value
    return fields


def _get_tarifa_text(soup: BeautifulSoup) -> str | None:
    """Get the main tarifa text from detail page (from .desk-para or plain text)."""
    lft = soup.select(".esp-det-lft")
    rgt = soup.select(".esp-det-rgt")
    for label_el, value_el in zip(lft, rgt):
        label = label_el.get_text(strip=True).upper()
        if label == "TARIFA":
            para = value_el.select_one(".desk-para")
            if para:
                return para.get_text(strip=True)
            return value_el.get_text(strip=True) or None
    return None


def _slug_from_url(url: str) -> str:
    """Extract the slug from a /espectacle/<slug>/ or /activitat/<slug>/ URL."""
    path = urllib.parse.urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1]


def _is_kids_event(title: str, url: str) -> bool:
    """True if the event is part of the children's programme."""
    combined = (title + " " + url).lower()
    return any(
        marker in combined
        for marker in ("elpetit", "el petit", "funcions escolars", "familiar")
    )


def _parse_dte_list(soup: BeautifulSoup, slug: str) -> list[ScrapedEvent]:
    """Parse .dte-lst items into per-occurrence ScrapedEvents (when tickets are live)."""
    events = []
    for li in soup.select(".dte-lst li"):
        text = li.get_text(" ", strip=True)
        parsed = _parse_dte_item(text)
        if not parsed:
            continue
        date, time = parsed
        # Get Patronbase prod_id + perf_id from link href
        a = li.select_one("a")
        pb_ext_id = None
        if a and "patronbase.com" in a.get("href", ""):
            href = a["href"]
            pm = re.search(r"prod_id=(\d+).*?perf_id=(\d+)", href)
            if pm:
                pb_ext_id = f"{pm.group(1)}_{pm.group(2)}"
        ext_id = pb_ext_id or f"{slug}@{date.isoformat()}T{time.strftime('%H%M')}"
        events.append((date, time, ext_id))
    return events


def parse_detail(html: str, source_url: str, list_date_text: str | None = None) -> dict:
    """Parse a detail page HTML and return structured event data."""
    soup = BeautifulSoup(html, "html.parser")
    slug = _slug_from_url(source_url)

    h1 = soup.select_one("h1")
    h2 = soup.select_one("h2")
    artist = h1.get_text(strip=True) if h1 else None
    title = h2.get_text(strip=True) if h2 else (artist or "")

    # If no meaningful title, fall back to slug
    if not title:
        title = slug

    # Get main image
    img = soup.select_one(".esp-img img, .hero-img img, .featured-image img")
    if not img:
        # Try og:image
        og = soup.select_one('meta[property="og:image"]')
        image_url = og.get("content") if og else None
    else:
        image_url = img.get("src")

    # Get fields
    tarifa_text = _get_tarifa_text(soup)
    price = _parse_price(tarifa_text)

    fields = _get_detail_fields(soup)
    horari = fields.get("HORARI")
    fallback_time = _parse_time(horari)

    # Description (sinopsis)
    sinopsis_el = soup.select_one(".sino-sec p")
    description = sinopsis_el.get_text(" ", strip=True) if sinopsis_el else None

    # Try .dte-lst first (per-occurrence, tickets live)
    dte_items = _parse_dte_list(soup, slug)

    # Falls back to text date from list or detail Dies field
    if not dte_items:
        # Check detail Dies field
        dies_text = fields.get("DIES") or list_date_text or ""
        dates = _parse_text_dates(dies_text)
        for d in dates:
            time = fallback_time
            ext_id_suffix = f"T{time.strftime('%H%M')}" if time else "T0000"
            ext_id = f"{slug}@{d.isoformat()}{ext_id_suffix}"
            dte_items.append((d, time, ext_id))

    return {
        "title": title,
        "artist": artist,
        "source_url": source_url,
        "price": price,
        "image_url": image_url,
        "description": description,
        "occurrences": dte_items,  # list of (date, time, ext_id)
        "horari": horari,
    }


def parse_agenda(html: str) -> list[tuple[str, str, str | None]]:
    """Parse the AJAX list HTML and return (detail_url, list_date_text, pb_id) tuples."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for card in soup.select(".mixitup-main"):
        a = card.select_one("a:first-child, a")
        if not a:
            continue
        href = a.get("href", "").split("?")[0].rstrip("/")
        if not href:
            continue
        # Ensure it's an absolute URL
        if not href.startswith("http"):
            href = BASE_URL + href

        h4 = card.select_one("h4")
        date_text = h4.get_text(strip=True) if h4 else None
        pb_id = card.get("data-patronbase") or None

        results.append((href, date_text, pb_id))
    return results


def _build_events(
    detail: dict,
    categories: list[str],
) -> list[ScrapedEvent]:
    """Build ScrapedEvent instances from parsed detail data."""
    events = []
    seen_ext_ids: set[str] = set()

    for date, time, ext_id in detail["occurrences"]:
        # Deduplicate within this show's occurrences
        if ext_id in seen_ext_ids:
            continue
        seen_ext_ids.add(ext_id)

        annotations = []
        if detail.get("artist"):
            annotations.append(detail["artist"])
        if detail.get("horari"):
            annotations.append(detail["horari"])

        events.append(
            ScrapedEvent(
                title=detail["title"],
                start_date=date,
                start_time=time,
                source_url=detail["source_url"],
                category_slugs=categories,
                price=detail["price"],
                image_url=detail["image_url"],
                description=detail["description"],
                external_id=ext_id,
                annotations=annotations,
            )
        )
    return events


class MercatFlorsScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        # Step 1: Fetch list of shows via AJAX
        list_html = self._fetch_list()
        show_refs = parse_agenda(list_html)

        # Step 2: Fetch each detail page
        events: list[ScrapedEvent] = []
        seen_ext_ids: set[str] = set()

        for detail_url, list_date_text, _pb_id in show_refs:
            try:
                detail_html = httpx.get(
                    detail_url, follow_redirects=True, timeout=30
                ).text
                detail = parse_detail(detail_html, detail_url, list_date_text)
            except Exception:
                continue

            # Determine categories
            cats = _determine_categories(detail["title"], detail_url)

            today = dt.date.today()
            for ev in _build_events(detail, cats):
                if ev.external_id in seen_ext_ids:
                    continue
                # Drop past occurrences — the AJAX endpoint returns the full season
                # (temporada_vista=1) with no date filter, so we filter client-side.
                if ev.start_date < today:
                    continue
                seen_ext_ids.add(ev.external_id)
                events.append(ev)

        return events

    def _fetch_list(self) -> str:
        """Fetch rendered show list from WordPress AJAX endpoint."""
        data = {
            "action": "carregar_directori",
            "posts_per_page": "100",
            "post_type[0]": "espectacle",
            "post_type[1]": "activitat",
            "page": "1",
            "order": "ASC",
            "post_status": "publish",
            "orderby": "meta_value",
            "meta_key": "dies_0_dia",
            "meta_query[relation]": "AND",
            "meta_query[0][relation]": "OR",
            "meta_query[1][key]": "temporada_vista",
            "meta_query[1][value]": "1",
            "tax_query[0][taxonomy]": "temporada",
            "tax_query[0][terms][0]": "8776",
            "language": "ca",
            "template-part": "content-espectacle",
        }
        r = httpx.post(AJAX_URL, data=data, timeout=30, follow_redirects=True)
        r.raise_for_status()
        resp = r.json()
        return resp["data"]["html"]


def _determine_categories(title: str, url: str) -> list[str]:
    cats = ["dance"]
    if _is_kids_event(title, url):
        cats.append("kids")
    return cats


register(
    scraper=MercatFlorsScraper(),
    venue=VenueDefinition(
        slug="mercat-flors",
        name="Mercat de les Flors",
        city_slug="barcelona",
        address="Plaça de Margarida Xirgu, 1, 08004 Barcelona",
        site_url="https://mercatflors.cat",
        category_slugs=["dance", "kids"],
        list_memberships=[
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
