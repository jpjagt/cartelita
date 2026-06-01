from __future__ import annotations
import datetime as dt
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent

# Sala Beckett (Poblenou, Barcelona) is a WordPress theatre site. There is NO
# usable JSON-LD event data — the only `application/ld+json` block is Yoast SEO
# boilerplate (WebPage/BreadcrumbList), no price/date/category. So we parse the
# rendered DOM cards directly. Both list pages render identical `.post` cards
# (title, sub-type, date(s), price, schedule, space, detail link), one card per
# show/activity, with no pagination, so each page is a complete single request.
ESPECTACLES_URL = "https://www.salabeckett.cat/espectacles/"
ACTIVITATS_URL = "https://www.salabeckett.cat/activitats/"
LIST_URLS = (ESPECTACLES_URL, ACTIVITATS_URL)
BASE_URL = "https://www.salabeckett.cat"
VENUE_SLUG = "sala-beckett"
JAZZ_CICLE_URL = "https://www.salabeckett.cat/es/activitat-resta/cicle-de-jazz-el-menjador-de-la-beckett/"
LOOKAHEAD_DAYS = 14

# Sala Beckett is a theatre / performing-arts venue: every event maps to
# `theater`. Should the venue ever programme a music concert, the card's
# post-type (e.g. "Concert") would flag it — mapped to `jazz`. The post-type
# label (Espectacle, Recital, Mostra, Xerrada, ...) is a too-granular format
# tag, kept as a free-form annotation rather than a top-level category.
_MUSIC_TYPES = {"concert", "concerts", "música", "musica"}

# Some activitats aren't open calendar events: closed to the public, or
# reserved for the venue's members ("Personatges de la Beckett"). When either
# marker shows up in the title, subtitle, or price, we drop the event entirely.
_EXCLUDE_MARKERS = (
    "tancada al públic",
    "exclusiva per als personatges",
)

_DDMMYYYY = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
# A clock time like "20 h", "21:30 h", "18.30 h", "18h" — the hour, optional
# minutes (':' or '.'), then the 'h' marker.
_TIME = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*h\b", re.IGNORECASE)

_FREE_MARKERS = re.compile(r"gratu[ïi]?t", re.IGNORECASE)
_BUNDLED_MARKERS = re.compile(r"inclòs|preu de l'entrada", re.IGNORECASE)
_PRICE_NUM = re.compile(r"(\d+)\s*€")


def _parse_price(raw: str | None) -> str | None:
    if not raw:
        return None
    if _FREE_MARKERS.search(raw):
        return "free"
    if _BUNDLED_MARKERS.search(raw):
        return "free"
    nums = [int(m.group(1)) for m in _PRICE_NUM.finditer(raw)]
    if nums:
        return f"{max(nums)}€"
    return None


def assert_jazz_cicle_season(html: str) -> None:
    """Raise if the Jazz cicle page no longer states the expected season."""
    if "desde septiembre hasta julio" not in html.lower():
        raise ValueError(
            "Sala Beckett Jazz cicle assumption changed — check season dates at "
            f"{JAZZ_CICLE_URL}"
        )


def generate_jazz_hour_events(today: dt.date | None = None) -> list[ScrapedEvent]:
    """Emit Sunday Jazz Hour events for the next LOOKAHEAD_DAYS days (skipping August)."""
    if today is None:
        today = dt.date.today()
    events: list[ScrapedEvent] = []
    for offset in range(LOOKAHEAD_DAYS):
        date = today + dt.timedelta(days=offset)
        if date.weekday() != 6 or date.month == 8:
            continue
        events.append(
            ScrapedEvent(
                title="Cicle de Jazz — El Menjador de la Beckett",
                start_date=date,
                start_time=dt.time(12, 0),
                end_time=dt.time(13, 0),
                source_url=JAZZ_CICLE_URL,
                category_slugs=["jazz"],
                price="free",
                external_id=f"sala-beckett-jazz-menjador-{date.isoformat()}",
            )
        )
    return events


def _normalize_url(url: str) -> str:
    url = url.split("?")[0].split("#")[0].rstrip("/")
    if url.startswith("/"):
        url = BASE_URL + url
    return url


def _extract_external_id(url: str) -> str | None:
    m = re.search(r"/(?:espectacle|activitat|projecte)/([^/?#]+)", url)
    return m.group(1) if m else None


def _card_field(card: Tag, label: str) -> str | None:
    """Return the trimmed text of the `.mini-content` whose `.mini-title` is
    `label` (e.g. 'Preu', 'Horari', 'Espai'), or None if absent/empty."""
    for mw in card.select(".mini-wrapper"):
        title = mw.select_one(".mini-title")
        if title and title.get_text(strip=True) == label:
            content = mw.select_one(".mini-content")
            text = content.get_text(" ", strip=True) if content else ""
            return text or None
    return None


def _parse_dates(text: str) -> tuple[dt.date, dt.date | None] | None:
    """Single date 'DD/MM/YYYY' -> (start, None); range 'Del DD/MM/YYYY al
    DD/MM/YYYY' (or Catalan-elided 'De l'..') -> (start, end). The first
    DD/MM/YYYY token is the start, the last is the end."""
    tokens = _DDMMYYYY.findall(text)
    if not tokens:
        return None
    dates = [dt.date(int(y), int(mo), int(d)) for d, mo, y in tokens]
    start = dates[0]
    end = dates[-1] if dates[-1] != start else None
    return start, end


def _parse_start_time(horari: str | None, is_range: bool) -> dt.time | None:
    """A single-day show lists one start time ('A les 20 h', '21:30 h', 'De 12 h
    a 1 h' -> first). A multi-day run lists a weekly schedule ('De dimecres a
    dissabte, 20 h …') whose per-day time is ambiguous, so we leave the time
    unknown (None) and keep the schedule as an annotation. Free-text horaris
    with no clock value ('Després de la funció …') -> None."""
    if not horari or is_range:
        return None
    m = _TIME.search(horari)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    if hour > 23 or minute > 59:
        return None
    return dt.time(hour, minute)


def _parse_cards(soup: BeautifulSoup) -> list[ScrapedEvent]:
    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for card in soup.select(".post"):
        link = card.select_one("a.title")
        if not link:
            continue
        title = link.get_text(" ", strip=True)
        source_url = _normalize_url(link.get("href", ""))
        if not title or not source_url or source_url in seen:
            continue
        seen.add(source_url)

        dates_el = card.select_one(".dates")
        if not dates_el:
            continue
        dates_text = dates_el.get_text(" ", strip=True)
        parsed = _parse_dates(dates_text)
        if not parsed:
            continue
        start_date, end_date = parsed
        is_range = end_date is not None

        horari = _card_field(card, "Horari")
        start_time = _parse_start_time(horari, is_range)

        post_type_el = card.select_one(".post-type")
        post_type = post_type_el.get_text(strip=True) if post_type_el else None
        is_music = bool(post_type and post_type.strip().lower() in _MUSIC_TYPES)
        category = "jazz" if is_music else "theater"

        subtitle_el = card.select_one(".subtitle")
        subtitle = subtitle_el.get_text(" ", strip=True) if subtitle_el else None
        raw_price = _card_field(card, "Preu")

        # Drop events that are closed to the public or members-only; the marker
        # can appear in the title, subtitle, or the price line.
        haystack = " ".join(filter(None, [title, subtitle, raw_price])).lower()
        if any(marker in haystack for marker in _EXCLUDE_MARKERS):
            continue

        price = _parse_price(raw_price)

        # Annotations: the format label, sub-title, and (for multi-day runs) the
        # weekly schedule and the space — context that's too granular for a
        # top-level category but worth surfacing.
        annotations: list[str] = []
        if post_type:
            annotations.append(post_type)
        if subtitle:
            annotations.append(subtitle)
        if is_range and horari:
            annotations.append(horari)
        espai = _card_field(card, "Espai")
        if espai:
            annotations.append(espai)

        img = card.select_one("a.image img")
        image_url = img.get("src") if img else None

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                end_date=end_date,
                end_time=None,
                source_url=source_url,
                category_slugs=[category],
                price=price,
                image_url=image_url or None,
                external_id=_extract_external_id(source_url),
                recurrence_hint=None,
                annotations=annotations,
            )
        )
    return events


def parse_agenda(html: str) -> list[ScrapedEvent]:
    """Parse one Sala Beckett list page (espectacles or activitats) into
    ScrapedEvents. Each `.post` card carries title, date(s), price, schedule and
    a detail link; there is no event JSON-LD on this site, so the cards are the
    sole source. Category is `theater` for everything (the venue is a theatre),
    `jazz` only if a card's post-type marks it a music concert."""
    return _parse_cards(BeautifulSoup(html, "html.parser"))


class SalaBeckettScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        seen: set[str] = set()
        for url in LIST_URLS:
            html = httpx.get(url, follow_redirects=True, timeout=30).text
            for ev in parse_agenda(html):
                if ev.source_url in seen:
                    continue
                seen.add(ev.source_url)
                events.append(ev)
        # Jazz Hour: fetch cicle page to assert assumption, then emit static events.
        cicle_html = httpx.get(JAZZ_CICLE_URL, follow_redirects=True, timeout=30).text
        assert_jazz_cicle_season(cicle_html)
        events.extend(generate_jazz_hour_events())
        return events


register(SalaBeckettScraper())
