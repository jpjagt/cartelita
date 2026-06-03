from __future__ import annotations
import datetime as dt
import html as html_module
import re
import unicodedata

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Cinema Maldà — independent VOSE/VOSCAT cinema in Barcelona's Gothic Quarter.
# The "day-by-day" page (`/cartelera-dia-dia/`) server-renders the current week's
# schedule as plain paragraphs: one `<p>` per day, opening with an orange day
# heading ("MARTES 2") followed by `<br/>`-separated `HH:MMh – TITLE (VO…)` lines.
# That page is the authoritative source of date+time+title (one request covers the
# whole week). The homepage card grid carries per-film detail links + posters but
# inconsistent free-text showtimes, so we read it only to resolve a film slug →
# detail URL / poster for each title. See cinema_malda_SOURCE.md.
BASE_URL = "https://www.cinemamalda.com"
AGENDA_URL = f"{BASE_URL}/cartelera-dia-dia/"
HOME_URL = f"{BASE_URL}/"
PRICES_URL = f"{BASE_URL}/precios-cine-malda-barcelona-preus/"
VENUE_SLUG = "cinema-malda"

# Default per-weekday price if the prices page can't be read (concise range).
_DEFAULT_PRICE = "5,90–9€"

_ES_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
# Spanish weekday name (in the day heading) -> Python weekday (Mon=0). Used only
# as a sanity check; the day-of-month is authoritative.
_ES_WEEKDAYS = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4,
    "sabado": 5, "domingo": 6,
}

_HEADER_RE = re.compile(
    r"\bDE\s+([A-Za-zÁÉÍÓÚáéíóúñ]+)\s+DE\s+(\d{4})", re.I
)
_DAY_HEADING_RE = re.compile(
    r"^\s*([A-Za-zÁÉÍÓÚáéíóúñ]+)\s+(\d{1,2})\b", re.I
)
_SESSION_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*h\b\s*[–-]\s*(.+)$")
_VO_TAG_RE = re.compile(r"\((VO[^)]*)\)", re.I)
_PRICE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*€")


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").strip()


def _strip_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def slugify_title(title: str) -> str:
    """Slugify a session title to the venue's detail-page slug.

    Drops parenthetical tags ((VOSE), (ESTRENO), …) then lowercases/ascii-folds
    and hyphenates — this matches the homepage detail-page slugs exactly
    (e.g. "UYARIY (ESCUCHAR) (VOE) (ESTRENO)" -> "uyariy")."""
    s = re.sub(r"\([^)]*\)", "", title)
    s = _strip_accents(s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def _title_and_annotation(raw: str) -> tuple[str, list[str]]:
    """Split a session line's text into a clean title + VO-tag annotation.

    Title is the text up to the first parenthetical; the original-version tag
    (VOSE/VOE/VOSCAT/VOCAT) is captured as an annotation. Other trailing notes
    (ESTRENO, sessió-continua warnings) are dropped from the title."""
    raw = _clean(raw)
    vo = _VO_TAG_RE.search(raw)
    annotations = [vo.group(1).upper()] if vo else []
    # Title = everything before the first "(" (the VO/other tags), trimmed.
    title = raw.split("(", 1)[0].strip(" –-")
    return title or raw, annotations


def parse_prices(html: str) -> dict[int, str]:
    """Per-weekday price map (Mon=0…Sun=6) from the prices page.

    The page lists a flat per-DAY admission that varies by weekday
    (e.g. LUNES – 5,90€, MARTES – 7,50€, SÁBADO – 9 €). FESTIVOS (holidays) shares
    the Saturday tier; Sunday is mapped to that tier too (the page lists FESTIVOS,
    not DOMINGO)."""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".entry-content") or soup
    text = content.get_text("\n", strip=True)
    lines = [_clean(l) for l in text.split("\n") if _clean(l)]

    out: dict[int, str] = {}
    sat_price: str | None = None
    # Walk lines, attaching the next price found after a weekday label to it.
    i = 0
    while i < len(lines):
        label = _strip_accents(lines[i]).lower()
        wd = next((w for k, w in _ES_WEEKDAYS.items() if label.startswith(k)), None)
        is_festivos = label.startswith("festivos")
        if wd is not None or is_festivos:
            # Find the price within this line or the next few lines.
            price = None
            for j in range(i, min(i + 6, len(lines))):
                m = _PRICE_RE.search(lines[j])
                if m:
                    price = f"{m.group(1)}€"
                    break
            if price:
                if wd is not None:
                    out[wd] = price
                if is_festivos or wd == 5:
                    sat_price = price
        i += 1
    # Sunday shares the Saturday / holiday tier.
    if 6 not in out and sat_price:
        out[6] = sat_price
    return out


def _build_home_index(html: str) -> tuple[set[str], dict[str, str], dict[str, str]]:
    """From the homepage: (detail-page slugs, slug->poster URL, slug->title).

    The homepage `h3` titles are nicely title-cased ("Tres adioses"), whereas the
    day-by-day schedule renders them ALL-CAPS — so we use the homepage title for
    display when the slug resolves."""
    soup = BeautifulSoup(html, "html.parser")
    slugs: set[str] = set()
    images: dict[str, str] = {}
    titles: dict[str, str] = {}
    for a in soup.select(".movies a.movie"):
        href = a.get("href", "")
        m = re.match(rf"{re.escape(BASE_URL)}/([a-z0-9][a-z0-9_-]*)/?$", href)
        if not m:
            continue
        slug = m.group(1)
        slugs.add(slug)
        img = a.select_one(".img img")
        src = (img.get("data-src") or img.get("src") or "") if img else ""
        if src and not src.startswith("data:"):
            images[slug] = src
        h3 = a.select_one("h3")
        if h3:
            title, _ = _title_and_annotation(h3.get_text(" ", strip=True))
            if title:
                titles[slug] = title
    return slugs, images, titles


def _header_month_year(sinopsi: Tag) -> tuple[int | None, int | None]:
    """Month + year from the `<h2>` week header ("… DE JUNIO DE 2026")."""
    h2 = sinopsi.find("h2")
    if not h2:
        return None, None
    m = _HEADER_RE.search(_clean(h2.get_text(" ", strip=True)))
    if not m:
        return None, None
    month = _ES_MONTHS.get(_strip_accents(m.group(1)).lower())
    year = int(m.group(2))
    return month, year


def _day_paragraphs(sinopsi: Tag) -> list[tuple[int, list[str]]]:
    """Each schedule `<p>` -> (day-of-month, [session-line strings]).

    The `<p>` opens with the orange day heading then `<br/>`-separated lines; we
    split the paragraph's text on newlines (bs4 renders `<br/>` as a separator)."""
    out: list[tuple[int, list[str]]] = []
    for p in sinopsi.find_all("p"):
        # Day-of-month from the orange heading span (fallback: first line).
        heading = p.find("span", style=re.compile("ff6600", re.I))
        heading_text = _clean(heading.get_text(" ", strip=True)) if heading else ""
        lines = [_clean(l) for l in p.get_text("\n").split("\n")]
        lines = [l for l in lines if l]
        if not heading_text and lines:
            heading_text = lines[0]
        dm = _DAY_HEADING_RE.match(heading_text)
        if not dm:
            continue
        day_of_month = int(dm.group(2))
        out.append((day_of_month, lines))
    return out


def parse_agenda(
    html: str,
    slugs: set[str] | None = None,
    images: dict[str, str] | None = None,
    prices: dict[int, str] | None = None,
    titles: dict[str, str] | None = None,
) -> list[ScrapedEvent]:
    """Parse the Cinema Maldà day-by-day page into ScrapedEvents.

    One ScrapedEvent per session line. Date = day-of-month (from each day's orange
    heading) + month/year (from the `<h2>` week header, rolled forward across a
    month boundary). Title/time from the `HH:MMh – TITLE` line; the VO tag becomes
    an annotation. `source_url` resolves to the film's detail page when the title's
    slug is in `slugs` (else the day-by-day page); `prices` (weekday->price) sets
    the per-screening price."""
    slugs = slugs or set()
    images = images or {}
    prices = prices or {}
    titles = titles or {}

    soup = BeautifulSoup(html, "html.parser")
    sinopsi = soup.select_one(".entry-content .sinopsi") or soup
    month, year = _header_month_year(sinopsi)
    if month is None or year is None:
        return []

    events: list[ScrapedEvent] = []
    prev_day = 0
    cur_month, cur_year = month, year
    for day_of_month, lines in _day_paragraphs(sinopsi):
        # Roll month/year forward when the day-of-month wraps (week straddles a
        # month boundary, e.g. 30, 31, 1, 2).
        if day_of_month < prev_day:
            if cur_month == 12:
                cur_month, cur_year = 1, cur_year + 1
            else:
                cur_month += 1
        prev_day = day_of_month
        try:
            day = dt.date(cur_year, cur_month, day_of_month)
        except ValueError:
            continue

        for line in lines:
            sm = _SESSION_RE.match(line)
            if not sm:
                continue
            hh, mm = int(sm.group(1)), int(sm.group(2))
            if not (0 <= hh < 24 and 0 <= mm < 60):
                continue
            start_time = dt.time(hh, mm)
            title, annotations = _title_and_annotation(sm.group(3))
            if not title:
                continue

            slug = slugify_title(title)
            resolved = slug in slugs
            source_url = f"{BASE_URL}/{slug}/" if resolved else AGENDA_URL
            image_url = images.get(slug)
            # The day-by-day page is ALL-CAPS; prefer the homepage's title-cased
            # name when the slug resolves.
            if resolved and slug in titles:
                title = titles[slug]
            id_slug = slug or "session"
            external_id = f"{id_slug}@{day.isoformat()}T{start_time.strftime('%H%M')}"

            events.append(
                ScrapedEvent(
                    title=title,
                    start_date=day,
                    start_time=start_time,
                    source_url=source_url,
                    category_slugs=["film"],
                    price=prices.get(day.weekday()),
                    image_url=image_url,
                    external_id=external_id,
                    annotations=annotations,
                )
            )
    return events


class CinemaMaldaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            agenda_html = client.get(AGENDA_URL).text
            try:
                slugs, images, titles = _build_home_index(client.get(HOME_URL).text)
            except httpx.HTTPError:
                slugs, images, titles = set(), {}, {}
            try:
                prices = parse_prices(client.get(PRICES_URL).text)
            except httpx.HTTPError:
                prices = {}
        return parse_agenda(
            agenda_html, slugs=slugs, images=images, prices=prices, titles=titles
        )


register(
    scraper=CinemaMaldaScraper(),
    venue=VenueDefinition(
        slug="cinema-malda",
        name="Cinema Maldà",
        city_slug="barcelona",
        address="Carrer del Pi, 5, Ciutat Vella, 08002 Barcelona",
        site_url="https://www.cinemamalda.com",
        category_slugs=["film"],
        list_memberships=[
            ListMembership(list_slug="film"),
        ],
    ),
)
