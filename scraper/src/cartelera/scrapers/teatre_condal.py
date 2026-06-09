"""Teatre Condal (Paral·lel, Barcelona) — DOM scraper.

Data sources
------------
Season list:  https://www.teatrecondal.cat/ca/season/
              10 `article.espectacle-query__item` cards, each with a title,
              a detail link, a poster image, and `dis_N` discipline classes.
              The card also carries a human-readable Catalan date range
              (e.g. "del 22 de juliol al 2 d'agost de 2026") used as a
              fallback when the detail page has no individual sessions listed.

Detail pages: https://www.teatrecondal.cat/ca/ex/<slug>/
              `ul.espectacle_funciones` lists individual sessions as
              `<li><span class="date">DAY, DD/MM/YYYY - HH:MM</span><a href=".../select/<ID>">Comprar</a></li>`.
              The oneboxtds session ID in the purchase href is a stable,
              per-occurrence identifier used as `external_id`.
              Some shows (e.g. those with many sessions) have an empty
              `.espectacle_funciones` list and only a link to the full ticket
              platform. For those, a single event with the date range from
              the season card is emitted as a fallback.

Price: NOT available on the venue site. Prices are only on the external
       ticketing platform (tickets.oneboxtds.com) — price is left `None`.

Category mapping (dis_N discipline class → cartelera category):
  dis_1  Musical        → theater
  dis_2  Dansa / Ballet → dance
  dis_7  Comèdia        → theater
  dis_8  Concert        → theater (chorus concerts are performed theatre pieces)
  dis_11 Teatre         → theater
  dis_12 Monòlegs       → theater
  dis_17 Tragicomèdia   → theater
  (any unknown dis_N)   → theater (safe default for a theater venue)

external_id: "teatre-condal:<session_id>" where session_id is the oneboxtds
             `/select/<ID>` integer, unique per occurrence. Falls back to
             "<slug>@<date>T<HHMM>" when the session list has no purchase links,
             or "<slug>@<start_date>" for the date-range fallback events.

Skipped: abonament/bundle items (no `.date` span in any `li`) are not
         performances; they are subscription packages and are excluded.

Last verified: 2026-06-09
"""
from __future__ import annotations

import datetime as dt
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

SEASON_URL = "https://www.teatrecondal.cat/ca/season/"
BASE_URL = "https://www.teatrecondal.cat"
VENUE_SLUG = "teatre-condal"

# DD/MM/YYYY - HH:MM (in session list on detail page)
_SESSION_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{2}):(\d{2})")
# oneboxtds /select/<id>
_SESSION_ID = re.compile(r"/select/(\d+)")
# dis_N discipline class
_DIS_CLASS = re.compile(r"\bdis_(\d+)\b")
# show slug from detail URL
_SLUG = re.compile(r"/ex/([^/?#]+)/")

# Catalan month names → int
_CAT_MONTH = {
    "gener": 1, "febrer": 2, "marc": 3, "abril": 4,
    "maig": 5, "juny": 6, "juliol": 7, "agost": 8,
    "setembre": 9, "octubre": 10, "novembre": 11, "desembre": 12,
}
_MONTH_PATTERN = "gener|febrer|mar[çc]|abril|maig|juny|juliol|agost|setembre|octubre|novembre|desembre"
# Both straight apostrophe (U+0027) and right single quotation mark (U+2019)
_APO = "['\\u2019]"
# Matches: <day> (de/d'/d') <month> [de <year>]
_DATE_WITH_MONTH = re.compile(
    rf"(\d{{1,2}})\s+(?:de?{_APO}?)\s*({_MONTH_PATTERN})(?:\s+de\s+(\d{{4}}))?",
    re.IGNORECASE,
)
# Matches a range-start day-only: 'del N al' or "de l'N al" / "de l'N al" (no month given)
_RANGE_START_DAY = re.compile(
    rf"(?:del?\s+|de\s+l{_APO}\s*)\s*(\d{{1,2}})(?:\s+al|\s+fins)",
    re.IGNORECASE,
)

# Titles that start with these prefixes are bundle/subscription products,
# not individual performances — skip them entirely.
_BUNDLE_TITLE_PREFIXES = ("ABONAMENT", "ABONO", "PACK ")

# dis_N → cartelera category slug
_DIS_TO_CATEGORY: dict[str, str] = {
    "1": "theater",   # Musical
    "2": "dance",     # Dansa / Ballet
    "7": "theater",   # Comèdia
    "8": "theater",   # Concert (choral/theater concert)
    "11": "theater",  # Teatre
    "12": "theater",  # Monòlegs
    "17": "theater",  # Tragicomèdia
}


def _category_from_classes(classes: list[str]) -> str:
    for cls in classes:
        m = _DIS_CLASS.match(cls)
        if m:
            return _DIS_TO_CATEGORY.get(m.group(1), "theater")
    return "theater"


def _parse_catalan_date_range(
    text: str,
) -> tuple[dt.date | None, dt.date | None]:
    """Parse a Catalan date range string into (start, end).

    Handles:
    - 'fins al 28 de juny de 2026'     → (2026-06-28, None)
    - 'del 17 al 21 de juny de 2026'   → (2026-06-17, 2026-06-21)
    - "de l'1 de juliol al 2 d'agost"  → (2026-07-01, 2026-08-02)
    - "el 19 d'octubre de 2026"        → (2026-10-19, None)
    - 'del 12 de febrer al 14 de març de 2027' → (2027-02-12, 2027-03-14)
    """
    dated = list(_DATE_WITH_MONTH.finditer(text))
    if not dated:
        return None, None

    # Find the year from the last dated element with a year
    last_year: int | None = None
    for m in reversed(dated):
        if m.group(3):
            last_year = int(m.group(3))
            break
    if last_year is None:
        return None, None

    resolved: list[dt.date] = []
    for m in dated:
        day_s, month_s, year_s = m.groups()
        year = int(year_s) if year_s else last_year
        month_norm = month_s.lower().replace("ç", "c")
        month = _CAT_MONTH.get(month_norm)
        if month is None:
            continue
        resolved.append(dt.date(year, month, int(day_s)))

    # Check for a bare day-only range start preceding the first full date
    # e.g. 'del 17 al 21 de juny de 2026' → '17' precedes '21 de juny'
    if dated:
        first_pos = dated[0].start()
        preceding = text[:first_pos]
        m2 = _RANGE_START_DAY.search(preceding)
        if m2:
            start_day = int(m2.group(1))
            first_full = resolved[0]
            start = dt.date(first_full.year, first_full.month, start_day)
            resolved.insert(0, start)

    if not resolved:
        return None, None
    if len(resolved) == 1:
        return resolved[0], None
    return resolved[0], resolved[-1]


def _slug_from_url(url: str) -> str | None:
    m = _SLUG.search(url)
    return m.group(1) if m else None


def _parse_detail(
    html: str,
    title: str,
    source_url: str,
    category: str,
    image_url: str | None,
    dates_text: str | None = None,
) -> list[ScrapedEvent]:
    """Parse one Teatre Condal detail page into per-session ScrapedEvents.

    If the `.espectacle_funciones` list is empty (some high-session shows
    omit per-session links), falls back to a single event using the date
    range text from the season card (passed as `dates_text`).
    """
    soup = BeautifulSoup(html, "html.parser")
    ul = soup.select_one(".espectacle_funciones")
    slug = _slug_from_url(source_url) or "show"
    events: list[ScrapedEvent] = []

    if ul:
        for li in ul.select("li:not(.other_dates)"):
            date_span = li.select_one(".date")
            if not date_span:
                # abonament / bundle line — no date, skip
                continue
            date_text = date_span.get_text(strip=True)
            m = _SESSION_DATE.search(date_text)
            if not m:
                continue
            day, month, year, hour, minute = m.groups()
            start_date = dt.date(int(year), int(month), int(day))
            start_time = dt.time(int(hour), int(minute))

            # external_id: prefer the per-session oneboxtds ID
            link = li.select_one("a")
            href = link.get("href", "") if link else ""
            id_match = _SESSION_ID.search(href)
            if id_match:
                external_id = f"teatre-condal:{id_match.group(1)}"
            else:
                # fallback: slug + date + time
                external_id = f"{slug}@{start_date.isoformat()}T{hour}{minute}"

            events.append(
                ScrapedEvent(
                    title=title,
                    start_date=start_date,
                    start_time=start_time,
                    source_url=source_url,
                    category_slugs=[category],
                    price=None,  # not on the venue site
                    image_url=image_url,
                    external_id=external_id,
                )
            )

    if not events and dates_text:
        # Fallback: emit a single date-range event from the season card text
        start_date, end_date = _parse_catalan_date_range(dates_text)
        if start_date:
            events.append(
                ScrapedEvent(
                    title=title,
                    start_date=start_date,
                    end_date=end_date,
                    source_url=source_url,
                    category_slugs=[category],
                    price=None,
                    image_url=image_url,
                    external_id=f"{slug}@{start_date.isoformat()}",
                )
            )

    return events


def parse_season(html: str) -> list[dict]:
    """Parse the season listing page into a list of show dicts (no network).

    Each dict has: title, url, category, image_url, slug, dates_text.
    `dates_text` is the human-readable Catalan date range from the season
    card (e.g. "del 22 de juliol al 2 d'agost de 2026") and is used as a
    fallback when a detail page has no individual sessions listed.
    """
    soup = BeautifulSoup(html, "html.parser")
    shows: list[dict] = []
    for article in soup.select("article.espectacle-query__item"):
        title_el = article.select_one(".title a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        url = title_el.get("href", "")
        if not url:
            continue
        # Skip subscription bundles (e.g. "ABONAMENT KULUNKA")
        if any(title.upper().startswith(p) for p in _BUNDLE_TITLE_PREFIXES):
            continue

        classes = article.get("class", [])
        category = _category_from_classes(classes)

        img_el = article.select_one("img")
        image_url = img_el.get("src") if img_el else None

        dates_el = article.select_one(".dates")
        dates_text = dates_el.get_text(strip=True) if dates_el else None

        shows.append(
            {
                "title": title,
                "url": url,
                "category": category,
                "image_url": image_url,
                "slug": _slug_from_url(url) or title.lower(),
                "dates_text": dates_text,
            }
        )
    return shows


def parse_detail(html: str, show: dict) -> list[ScrapedEvent]:
    """Parse a detail page using the show metadata from the season list."""
    return _parse_detail(
        html=html,
        title=show["title"],
        source_url=show["url"],
        category=show["category"],
        image_url=show.get("image_url"),
        dates_text=show.get("dates_text"),
    )


class TeatreCondalScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        season_html = httpx.get(SEASON_URL, follow_redirects=True, timeout=30).text
        shows = parse_season(season_html)

        events: list[ScrapedEvent] = []
        for show in shows:
            detail_html = httpx.get(
                show["url"], follow_redirects=True, timeout=30
            ).text
            events.extend(parse_detail(detail_html, show))

        return events


register(
    scraper=TeatreCondalScraper(),
    venue=VenueDefinition(
        slug="teatre-condal",
        name="Teatre Condal",
        city_slug="barcelona",
        address="C/ de la Creu dels Molers, 7, 08004 Barcelona",
        site_url="https://www.teatrecondal.cat",
        category_slugs=["theater", "dance"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
        ],
    ),
)
