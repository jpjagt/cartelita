from __future__ import annotations
import datetime as dt
import html as html_module
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent

# Harlem Jazz Club runs WordPress + EventON. The `/conciertos/` page server-renders
# the WHOLE upcoming agenda (currently ~42 events across several months) as EventON
# `.eventon_list_event` cards — far more than the homepage, which only ships the
# next handful and lazy-loads the rest client-side. This single page is the source.
#
# Each card's microdata carries a `data-time` (unix start/stop), a detail URL, an
# image, and a `.event-price`. We DON'T trust `.event-price` (it disagrees with the
# human-facing price — e.g. it reads "10" where the title says "11€"). Instead the
# real title, showtime, genres and price all live in the card title string, which
# is consistently formatted as:  "HH:MMh | NAME (genre, genre, ...) PRICE".
AGENDA_URL = "https://www.harlemjazzclub.es/conciertos/"
BASE_URL = "https://www.harlemjazzclub.es"
VENUE_SLUG = "harlem-jazz-club"

# Barcelona wall-clock is UTC+1/+2; EventON's data-time is a unix timestamp, so we
# convert in that zone to get the local calendar date.
_BARCELONA = dt.timezone(dt.timedelta(hours=2))

# Title prefix "22:30h | " — the real showtime (the data-time/startDate is the
# earlier bar-opening time, not the concert time).
_TIME_PREFIX = re.compile(r"^\s*(\d{1,2}):(\d{2})h\s*\|\s*")
# Free-entry markers used in place of a numeric price.
_FREE = re.compile(r"(entrada\s+libre|gratis|gratu(?:ï|i)t|lliure)", re.IGNORECASE)
# Trailing price token, e.g. "15€", "11 €".
_PRICE = re.compile(r"(\d+\s*€)\s*$")
# Genre annotations live in the LAST parenthesised group of the (de-prefixed) title.
_PARENS = re.compile(r"\(([^()]*)\)")


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").strip()


def _card_title(card: Tag) -> str | None:
    """The card's human title. Prefer the rendered `.evcal_event_title`; some cards
    omit it, so fall back to the `name` field of the card's embedded JSON-LD (which
    can't always be JSON-parsed because its description embeds raw HTML, so we pull
    the name with a regex)."""
    el = card.select_one(".evcal_event_title")
    if el and el.get_text(strip=True):
        return _clean(el.get_text(strip=True))
    script = card.find("script", type="application/ld+json")
    if script and script.string:
        m = re.search(r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"', script.string)
        if m:
            return _clean(m.group(1))
    return None


def _card_url(card: Tag) -> str | None:
    link = card.select_one('[itemprop="url"][href]')
    if not link:
        return None
    url = link.get("href", "").split("?")[0].rstrip("/")
    if url.startswith("/"):
        url = BASE_URL + url
    return url or None


def _card_date(card: Tag) -> dt.date | None:
    raw = card.get("data-time", "")
    start = raw.split("-")[0] if raw else ""
    if start.isdigit():
        return dt.datetime.fromtimestamp(int(start), _BARCELONA).date()
    # Fallback: the startDate meta (non-zero-padded ISO, e.g. "2026-6-2T20:30+2:00").
    meta = card.find("meta", attrs={"itemprop": "startDate"})
    content = meta.get("content") if meta else None
    if content:
        m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", content)
        if m:
            try:
                return dt.date(int(m[1]), int(m[2]), int(m[3]))
            except ValueError:
                return None
    return None


def _parse_title(raw: str) -> tuple[str, dt.time | None, str | None, list[str]]:
    """Split a card title into (clean_title, start_time, price, annotations).

    Format: "HH:MMh | NAME (genre, genre) PRICE". The time prefix, the genre parens
    and the trailing price are all stripped from the clean title."""
    start_time: dt.time | None = None
    m = _TIME_PREFIX.match(raw)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2))
        if 0 <= hh < 24 and 0 <= mm < 60:
            start_time = dt.time(hh, mm)
        raw = raw[m.end():]

    # Price: a free-entry phrase or a trailing "NN€" at the very end of the title.
    price: str | None = None
    free = _FREE.search(raw)
    if free:
        price = "free"
        raw = raw[: free.start()] + raw[free.end():]
    else:
        pm = _PRICE.search(raw)
        if pm:
            price = pm.group(1).replace(" ", "")
            raw = raw[: pm.start()]

    # Annotations: the genres in the last parenthesised group (split on commas).
    annotations: list[str] = []
    paren_spans = list(_PARENS.finditer(raw))
    if paren_spans:
        last = paren_spans[-1]
        annotations = [a.strip() for a in last.group(1).split(",") if a.strip()]
        raw = raw[: last.start()] + raw[last.end():]

    title = re.sub(r"\s+", " ", raw).strip(" -|·–").strip()
    return title, start_time, price, annotations


def _external_id(card: Tag, url: str | None) -> str | None:
    eid = card.get("data-event_id")
    if eid:
        return str(eid)
    if url:
        return url.rstrip("/").rsplit("/", 1)[-1] or None
    return None


def parse_agenda(html: str) -> list[ScrapedEvent]:
    """Parse the Harlem Jazz Club `/conciertos/` EventON list into ScrapedEvents.

    One ScrapedEvent per `.eventon_list_event` card with a title and detail URL.
    Title, showtime, price and genre annotations come from the title string; the
    date comes from the card's `data-time`. Every event is category `jazz` (the
    venue is a jazz/blues/swing concert hall with no club/DJ programming)."""
    soup = BeautifulSoup(html, "html.parser")

    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for card in soup.select(".eventon_list_event"):
        # Skip the hidden lightbox/popup template card (no url, no data-time).
        if "evo_lightbox_body" in (card.get("class") or []):
            continue

        url = _card_url(card)
        title_raw = _card_title(card)
        if not url or not title_raw:
            continue
        if url in seen:
            continue
        seen.add(url)

        start_date = _card_date(card)
        if start_date is None:
            continue  # no reliable date; skip rather than guess

        title, start_time, price, annotations = _parse_title(title_raw)
        if not title:
            continue

        image = card.find("meta", attrs={"itemprop": "image"})
        image_url = image.get("content") if image else None

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=url,
                category_slugs=["jazz"],
                price=price,
                image_url=image_url or None,
                external_id=_external_id(card, url),
                annotations=annotations,
            )
        )

    return events


class HarlemJazzClubScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        html = httpx.get(AGENDA_URL, follow_redirects=True, timeout=30).text
        return parse_agenda(html)


register(HarlemJazzClubScraper())
