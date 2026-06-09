"""Nau Ivanow (Sant Andreu, Barcelona) — WordPress custom post type scraper.

Data source: WordPress REST API (/wp-json/wp/v2/event) with full `content`
included. The site stores events as a custom post type `event`, split into two
taxonomy terms under `event_type`:
  - actes-oberts  (term id 12) — open activities / performances
  - formacio      (term id 11) — professional training workshops

There is NO structured date, time, or price field accessible via the API — all
three are embedded as free text inside the event's body HTML. This module parses
those free-text fields from the rendered content.

Date format: Catalan — "N de MONTH", "N d'MONTH" (curly or straight apostrophe),
often preceded by a weekday name. Year is inferred from the publication date: if
the (month, day) found is ≥ 30 days before the publication date it belongs to the
following year, otherwise the same year.

Price: "gratuït/gratuïtes/gratuïta" → "free"; digits+€ → plain display string;
"esgotad[ae]" / "Sold Out" → "sold-out"; otherwise None.

Multi-session formació workshops list multiple dates in the body (calendar list).
Each session emits as a separate ScrapedEvent with external_id = "{slug}@{date}".

Category mapping:
  - Title/content contains "taller familiar", "en famíl", "per a infants",
    "extraescolar", "escolars", "per a escoles" → kids
  - Otherwise → theater (this is a performing-arts residency space)

last verified: 2026-06-09
"""
from __future__ import annotations

import datetime as dt
import re
from html.parser import HTMLParser

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.scrapers.price import format_eur_range
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# ─── constants ────────────────────────────────────────────────────────────────

VENUE_SLUG = "nau-ivanow"
BASE_URL = "https://nauivanow.com"
API_URL = f"{BASE_URL}/wp-json/wp/v2/event"

# Fetch events published within the last LOOKBACK_DAYS days.
LOOKBACK_DAYS = 548  # ~18 months, covers seasonal programming

# Event type taxonomy IDs
EVENT_TYPE_ACTIVITATS = 12   # actes-oberts
EVENT_TYPE_FORMACIO = 11     # formació

# ─── Catalan date parsing ──────────────────────────────────────────────────────

_CATALAN_MONTHS: dict[str, int] = {
    "gener": 1, "febrer": 2, "marc": 3, "març": 3,
    "abril": 4, "maig": 5, "juny": 6,
    "juliol": 7, "agost": 8, "setembre": 9,
    "octubre": 10, "novembre": 11, "desembre": 12,
}

_MONTH_PAT = "|".join(_CATALAN_MONTHS.keys())

# Matches: "5 de juny", "5 d'abril", "5 d'octubre" (both straight and curly apostrophe)
_DATE_RE = re.compile(
    rf"(\d{{1,2}})\s+d[e’']\s*({_MONTH_PAT})",
    re.IGNORECASE,
)

# Time: "a les 17h", "a les 17:30h", "a les 19:00h",
# "d’11:00h a 12:30" (curly right-single-quote U+2019 before start; end h optional),
# "d’ 11 a 12:30h" (h only at end),
# "de 11h a 13h" (plain ‘de ... a ...’ range).
# The character class accepts ‘e’ (de), U+2019 curly right quote, or U+0027 straight apostrophe.
# Built with chr() to avoid editor apostrophe coercion.
# Guard against age ranges ("de 5 a 12 anys"): at least one ‘h’ must appear in the match.
# We achieve this with two alternates: one requiring h after start, one requiring h after end.
_APO_CLASS = "[e" + chr(0x2019) + chr(0x27) + "]"  # [e’’]
_TIME_RE = re.compile(
    r"a\s+les\s+(\d{1,2})(?::(\d{2}))?h"
    # start has h: "d’11:00h a 12:30" or "de 11h a 13h"
    r"|d" + _APO_CLASS + r"\s*(\d{1,2})(?::(\d{2}))?h\s+a\s+(\d{1,2})(?::(\d{2}))?h?"
    # end has h: "d’ 11 a 12:30h"
    r"|d" + _APO_CLASS + r"\s*(\d{1,2})(?::(\d{2}))?\s+a\s+(\d{1,2})(?::(\d{2}))?h",
    re.IGNORECASE,
)

# Price patterns
_FREE_RE = re.compile(
    r"gra[tu]+[ïi][ta]+|activitat\s+gra[tu]+[ïi][ta]+|entrada\s+gra[tu]+[ïi][ta]+|inscripcions?\s+gra[tu]+[ïi][ta]+",
    re.IGNORECASE,
)
_SOLDOUT_RE = re.compile(r"places?\s+esgotad[ae]+|sold.?out|esgotad[ae]+", re.IGNORECASE)
_EUR_RE = re.compile(r"(\d+(?:[,\.]\d+)?)\s*€|€\s*(\d+(?:[,\.]\d+)?)", re.IGNORECASE)


def _strip_html(html: str) -> str:
    """Return plain text from HTML, collapsing whitespace."""
    soup = BeautifulSoup(html, "html.parser")
    return " ".join(soup.get_text(" ", strip=True).split())


def _infer_year(day: int, month: int, pub_date: dt.date) -> dt.date | None:
    """Return the calendar date closest to/after pub_date for (day, month).

    Tries pub_year, then pub_year+1, then pub_year-1.  Accepts dates no more
    than 30 days before the publication date (event was in the past but
    recently described) or any date in the future relative to publication.
    """
    for offset in (0, 1, -1):
        try:
            candidate = dt.date(pub_date.year + offset, month, day)
        except ValueError:
            continue
        if candidate >= pub_date - dt.timedelta(days=30):
            return candidate
    return None


def _parse_dates(text: str, pub_date: dt.date) -> list[dt.date]:
    """Return all calendar dates found in *text*, resolved to a year via pub_date."""
    dates: list[dt.date] = []
    for day_str, month_str in _DATE_RE.findall(text):
        month = _CATALAN_MONTHS[month_str.lower()]
        d = _infer_year(int(day_str), month, pub_date)
        if d is not None:
            dates.append(d)
    return dates


def _parse_time(text: str) -> dt.time | None:
    """Return the first start time found in *text*, or None.

    Matches three patterns (ten capture groups total):
      - groups 1-2:   "a les 17h" / "a les 17:30h"
      - groups 3-6:   "d'11:00h a 12:30" / "de 11h a 13h" (h after start; start=3,4)
      - groups 7-10:  "d' 11 a 12:30h" (h after end; start=7,8)
    Returns the start hour in each case.
    """
    m = _TIME_RE.search(text)
    if not m:
        return None
    if m.group(1) is not None:
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
    elif m.group(3) is not None:
        hour, minute = int(m.group(3)), int(m.group(4) or 0)
    elif m.group(7) is not None:
        hour, minute = int(m.group(7)), int(m.group(8) or 0)
    else:
        return None
    if hour > 23 or minute > 59:
        return None
    return dt.time(hour, minute)


def _parse_price(text: str) -> str | None:
    """Extract a canonical price string from body text, or None if unknown."""
    if _SOLDOUT_RE.search(text):
        return "sold-out"
    nums = _EUR_RE.findall(text)
    if nums:
        # Each findall tuple has (group1, group2) — take the non-empty one
        values = []
        for g1, g2 in nums:
            raw = g1 or g2
            raw = raw.replace(",", ".")
            try:
                values.append(float(raw))
            except ValueError:
                pass
        if values:
            lo = min(int(v) for v in values)
            hi = max(int(v) for v in values)
            return format_eur_range(lo, hi)
    if _FREE_RE.search(text):
        return "free"
    return None


# ─── category logic ───────────────────────────────────────────────────────────

# Keywords that identify family/children events (category: kids)
_KIDS_RE = re.compile(
    r"taller\s+familiar|tallers?\s+en\s+famili|per\s+a\s+infants|"
    r"extraescolar|escolars?|per\s+a\s+escoles?|família",
    re.IGNORECASE,
)

# Keywords that suggest events should be skipped (not public / internal)
_SKIP_RE = re.compile(
    r"convocatòria\s+oberta|obrim\s+convocatòria|convocatoria\s+abierta",
    re.IGNORECASE,
)


def _categorize(title: str, text: str, event_type_ids: list[int]) -> list[str]:
    """Return category slug(s) for an event given its title, body text, and type ids."""
    if _KIDS_RE.search(title) or _KIDS_RE.search(text[:600]):
        return ["kids"]
    return ["theater"]


# ─── image URL extraction ─────────────────────────────────────────────────────

def _image_url(api_row: dict) -> str | None:
    """Extract an image URL for the event.

    Tries two sources in order:
    1. The UAGB block plugin field ``uagb_featured_image_src`` (a dict with
       'full', 'thumbnail', etc. keys whose values are [url, w, h, cropped]).
       This field is only populated in single-item responses, not in list
       responses with ``_fields`` filtering.
    2. The first ``<img>`` tag in ``content.rendered`` — always available.
    """
    src = api_row.get("uagb_featured_image_src")
    if isinstance(src, dict) and src:
        full = src.get("full") or src.get("medium_large") or src.get("thumbnail")
        if isinstance(full, list) and full and isinstance(full[0], str):
            return full[0]

    # Fallback: first <img> in body content
    content_html = api_row.get("content", {}).get("rendered", "")
    if content_html:
        soup = BeautifulSoup(content_html, "html.parser")
        img = soup.find("img")
        if img:
            url = img.get("src", "")
            if url and url.startswith("http"):
                return url
    return None


# ─── core parser ─────────────────────────────────────────────────────────────

def parse_api_events(api_rows: list[dict]) -> list[ScrapedEvent]:
    """Convert raw API rows (with ``content.rendered``) to ScrapedEvents.

    Multi-session workshops emit one event per session date. Events whose title
    or body signal an open call (convocatòria) are skipped — they are not public
    programme events. Events with no parseable date fall back to publication date.
    """
    events: list[ScrapedEvent] = []
    seen_ids: set[str] = set()

    for row in api_rows:
        title = BeautifulSoup(
            row.get("title", {}).get("rendered", ""), "html.parser"
        ).get_text(strip=True)
        if not title:
            continue

        link: str = row.get("link", "")
        slug: str = row.get("slug", "")
        pub_date: dt.date = dt.datetime.fromisoformat(row["date"]).date()
        event_type_ids: list[int] = row.get("event_type", [])
        content_html: str = row.get("content", {}).get("rendered", "")
        text = _strip_html(content_html)
        image_url = _image_url(row)

        # Skip open calls / convocatòries — they are administrative announcements
        if _SKIP_RE.search(title):
            continue

        category_slugs = _categorize(title, text, event_type_ids)
        price = _parse_price(text)

        dates = _parse_dates(text, pub_date)
        start_time = _parse_time(text)

        # Determine which date(s) to emit events for
        if not dates:
            # Fallback: publication date carries no info about the event date.
            # We use it so the event appears, but it may be slightly off.
            emit_dates = [pub_date]
        elif len(dates) == 1:
            emit_dates = dates[:1]
        else:
            # Multi-session: emit one event per unique date
            seen_d: set[dt.date] = set()
            emit_dates = []
            for d in dates:
                if d not in seen_d:
                    seen_d.add(d)
                    emit_dates.append(d)

        for event_date in emit_dates:
            # Per-occurrence external_id: slug + date (+ time if available)
            if start_time:
                ext_id = f"{slug}@{event_date.isoformat()}T{start_time.strftime('%H%M')}"
            else:
                ext_id = f"{slug}@{event_date.isoformat()}"

            if ext_id in seen_ids:
                continue
            seen_ids.add(ext_id)

            # For multi-session events use the slug as the description key
            annotations: list[str] = []
            if EVENT_TYPE_FORMACIO in event_type_ids:
                annotations.append("formació")

            events.append(
                ScrapedEvent(
                    title=title,
                    start_date=event_date,
                    start_time=start_time,
                    source_url=link,
                    category_slugs=category_slugs,
                    price=price,
                    image_url=image_url,
                    external_id=ext_id,
                    annotations=annotations,
                )
            )

    return events


# ─── scraper class ────────────────────────────────────────────────────────────

class NauIvanowScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        cutoff = (dt.date.today() - dt.timedelta(days=LOOKBACK_DAYS)).isoformat() + "T00:00:00"
        rows: list[dict] = []
        for term_id in (EVENT_TYPE_ACTIVITATS, EVENT_TYPE_FORMACIO):
            resp = httpx.get(
                API_URL,
                params={
                    "per_page": 100,
                    "_fields": "id,title,slug,date,link,event_type,content,uagb_featured_image_src",
                    "orderby": "date",
                    "order": "desc",
                    "after": cutoff,
                    "event_type": term_id,
                },
                follow_redirects=True,
                timeout=30,
            )
            resp.raise_for_status()
            rows.extend(resp.json())
        return parse_api_events(rows)


# ─── registration ─────────────────────────────────────────────────────────────

register(
    scraper=NauIvanowScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Nau Ivanow",
        city_slug="barcelona",
        address="C/ de les Hondures, 30, 08027 Barcelona",
        site_url=BASE_URL,
        category_slugs=["theater", "kids"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
