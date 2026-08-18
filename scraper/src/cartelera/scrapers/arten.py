from __future__ import annotations
import datetime as dt
import json
import re
from zoneinfo import ZoneInfo

import httpx

from cartelera.scrapers import register
from cartelera.scrapers.price import normalize_amd
from cartelera.types import (
    ScrapedEvent,
    ScrapedTranslation,
    VenueDefinition,
    ListMembership,
)

# arten — independent chamber theatre in Yerevan. Next.js site, trilingual
# (hy/ru/en); the programme page /{lang}/afisha lists one card per upcoming
# occurrence, server-rendered. We parse the RSC flight data (the
# self.__next_f.push script chunks), which carries a clean JSON array of card
# objects with a stable per-occurrence `key` embedding the date. hy is the
# canonical event content (Yerevan's default locale); ru/en afisha pages are
# zipped in by key as translations. See arten_SOURCE.md.
VENUE_SLUG = "arten"
BASE_URL = "https://www.arten.theater"
AFISHA_URL = BASE_URL + "/{lang}/afisha"

TZ = ZoneInfo("Asia/Yerevan")

# The display date string is "<localized date> · 14:30–16:00 · 2000 ֏" —
# segments separated by middle dots. No year (it lives in the card key).
_SEGMENT_SEP = "·"
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?:\s*[–—-]\s*(\d{1,2}):(\d{2}))?$")
_DATE_IN_KEY_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_RSC_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')

# "Free admission" phrasing per site language (none observed yet; defensive).
_FREE_WORDS = ("free", "бесплатно", "вход свободный", "անվճար")
_SOLD_OUT_WORDS = ("sold", "распрод", "վաճառ")


def _clean(text) -> str | None:
    # RSC serializes JS `undefined` as the sentinel string "$undefined".
    if not isinstance(text, str) or text == "$undefined":
        return None
    out = text.replace(" ", " ").strip()
    return out or None


def _decode_flight_blob(html: str) -> str:
    """Concatenate the RSC flight payload (each push chunk is a JSON string)."""
    parts = []
    for chunk in _RSC_CHUNK_RE.findall(html):
        parts.append(json.loads(f'"{chunk}"'))
    return "".join(parts)


def _extract_cards(html: str) -> list[dict]:
    """Find the afisha's `[{"key": ...}]` card array in the flight blob and
    parse it (bracket-scan so nested arrays/strings don't fool us)."""
    blob = _decode_flight_blob(html)
    start = blob.find('[{"key"')
    if start == -1:
        return []
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(blob)):
        ch = blob[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return json.loads(blob[start : i + 1])
    return []


def _parse_date_string(date_str: str | None) -> tuple[dt.time | None, dt.time | None, str | None]:
    """Split the display string into (start_time, end_time, raw price segment).
    The first segment is the localized date (year-less — ignored; the date
    comes from the card key)."""
    start = end = None
    price_raw = None
    for segment in (date_str or "").split(_SEGMENT_SEP)[1:]:
        segment = segment.replace(" ", " ").strip()
        m = _TIME_RE.match(segment)
        if m:
            start = dt.time(int(m.group(1)), int(m.group(2)))
            if m.group(3):
                end = dt.time(int(m.group(3)), int(m.group(4)))
        elif segment:
            price_raw = segment
    return start, end, price_raw


def _normalize_price(raw: str | None, status: str | None) -> str | None:
    if status and any(w in status.lower() for w in _SOLD_OUT_WORDS):
        return "sold-out"
    if not raw:
        return None
    if any(w in raw.lower() for w in _FREE_WORDS):
        return "free"
    out = normalize_amd(re.sub(r"\s+", " ", raw).strip())
    if re.fullmatch(r"0\s*֏", out):
        return "free"
    return out or None


def _date_from_key(key: str | None) -> dt.date | None:
    m = _DATE_IN_KEY_RE.search(key or "")
    return dt.date.fromisoformat(m.group(0)) if m else None


def _abs_url(path: str | None) -> str | None:
    path = _clean(path)
    if not path:
        return None
    if path.startswith("http"):
        return path
    return f"{BASE_URL}{path}"


def parse_afisha(
    hy_html: str,
    ru_html: str,
    en_html: str,
    today: dt.date | None = None,
) -> list[ScrapedEvent]:
    """Parse the three language versions of the afisha into one ScrapedEvent
    per occurrence. hy is canonical; ru/en cards join by `key` as translations.
    Everything the venue programmes maps to `theater` (no film/kids observed;
    see SOURCE.md). Past dates are filtered defensively."""
    if today is None:
        today = dt.datetime.now(TZ).date()

    translations_by_key: dict[str, list[ScrapedTranslation]] = {}
    for lang, html in (("ru", ru_html), ("en", en_html)):
        for card in _extract_cards(html):
            key = _clean(card.get("key"))
            title = _clean(card.get("title"))
            if not key or not title:
                continue
            translations_by_key.setdefault(key, []).append(
                ScrapedTranslation(
                    lang=lang,
                    title=title,
                    description=_clean(card.get("byline")),
                    source_url=_abs_url(card.get("href")),
                )
            )

    events: list[ScrapedEvent] = []
    for card in _extract_cards(hy_html):
        key = _clean(card.get("key"))
        title = _clean(card.get("title"))
        source_url = _abs_url(card.get("href"))
        start_date = _date_from_key(key)
        if not key or not title or not source_url or not start_date:
            continue
        if start_date < today:
            continue

        start_time, end_time, price_raw = _parse_date_string(_clean(card.get("date")))
        byline = _clean(card.get("byline"))
        annotations = [byline] if byline else []

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                start_times=[start_time] if start_time else [],
                end_time=end_time,
                source_url=source_url,
                category_slugs=["theater"],
                price=_normalize_price(price_raw, _clean(card.get("status"))),
                description=byline,
                image_url=_clean((card.get("photo") or {}).get("src")),
                external_id=f"arten-{key}",
                language=None,  # never stated per event on the site
                annotations=annotations,
                translations=translations_by_key.get(key, []),
            )
        )
    return events


class ArtenScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        pages = {
            lang: httpx.get(
                AFISHA_URL.format(lang=lang), follow_redirects=True, timeout=60
            ).text
            for lang in ("hy", "ru", "en")
        }
        return parse_afisha(pages["hy"], pages["ru"], pages["en"])


register(
    scraper=ArtenScraper(),
    venue=VenueDefinition(
        slug="arten",
        name="Arten",
        city_slug="yerevan",
        address="2 Lusinyants St, Yerevan",
        site_url="https://www.arten.theater",
        instagram_url="https://www.instagram.com/arten_theatre/",
        category_slugs=["theater"],
        list_memberships=[ListMembership(list_slug="theater")],
    ),
)
