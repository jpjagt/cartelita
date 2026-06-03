from __future__ import annotations
import datetime as dt
import html as html_module
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Ateneu Barcelonès — a cultural institution (Carrer de la Canuda, Barcelona). Its
# agenda is BROAD: most entries are talks, tertúlies, book launches and round
# tables. We want ONLY the (intimate, classical) music concerts in the `classical`
# calendar, so we filter on the venue's own activity-type discriminator and drop
# everything else.
#
# The live agenda is now on the migrated domain `https://ateneubcn.cat/programacio/`
# (the old `www.ateneubarcelones.cat` host's HTTPS is unresponsive and `/agenda`
# redirects to the homepage). The page server-renders a `.activitat` card per
# upcoming activity; each card carries the ISO date + local time as class tokens,
# the title, detail URL, activity type (`p.tipus`) and section (`p.e-chip`). The
# concert filter is the `tipus-11` class / `p.tipus == "Concerts"`.
#
# Price is NOT on the card — it lives on the detail page (`p.price.nosocis`), so
# `scrape()` fetches each concert's detail page (there are very few). See
# ateneu_barcelones_SOURCE.md.
AGENDA_URL = "https://ateneubcn.cat/programacio/"
BASE_URL = "https://ateneubcn.cat"
VENUE_SLUG = "ateneu-barcelones"

# The venue's own activity-type label for music concerts (also the `tipus-11`
# class). Used as the discriminator: only these become events.
CONCERT_TIPUS = "concerts"
CONCERT_TIPUS_CLASS = "tipus-11"

_DATE_CLASS = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_CLASS = re.compile(r"^(\d{1,2}):(\d{2})(?::\d{2})?$")
_PRICE_EUR = re.compile(r"(\d+(?:[.,]\d+)?)\s*€")

_FREE_PHRASES = ("gratuït", "gratuit", "gratis", "entrada lliure", "entrada libre")
_SOLD_OUT_PHRASES = ("exhaurid", "esgotad", "sold out", "s.o.")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").strip()


def _absolutize(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE_URL + url
    return url


def _is_concert(card: Tag) -> bool:
    """True iff the card is a music concert (the venue's `Concerts` activity type).

    Checks both the `tipus-11` class and the rendered `p.tipus` text, so a change to
    either one alone still flags the mismatch rather than silently dropping concerts."""
    classes = card.get("class", [])
    if CONCERT_TIPUS_CLASS in classes:
        return True
    tipus_el = card.select_one(".tipus")
    return bool(tipus_el and _clean(tipus_el.get_text()).lower() == CONCERT_TIPUS)


def _card_date(card: Tag) -> dt.date | None:
    """Occurrence date from the ISO class token on `.activitat` (e.g. `2026-06-10`)."""
    for cl in card.get("class", []):
        if _DATE_CLASS.match(cl):
            try:
                return dt.date.fromisoformat(cl)
            except ValueError:
                return None
    return None


def _card_time(card: Tag) -> dt.time | None:
    """Local showtime from the `HH:MM:SS` class token on `.activitat`."""
    for cl in card.get("class", []):
        m = _TIME_CLASS.match(cl)
        if m:
            hh, mm = int(m.group(1)), int(m.group(2))
            if 0 <= hh < 24 and 0 <= mm < 60:
                return dt.time(hh, mm)
    return None


def _slug_from_url(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def parse_agenda(
    html: str, prices: dict[str, str | None] | None = None
) -> list[ScrapedEvent]:
    """Parse the programació page into one ScrapedEvent per upcoming MUSIC concert.

    Only cards whose activity type is `Concerts` (the venue's discriminator) are
    emitted — every other activity (talks, tertúlies, book launches, round tables)
    is dropped, not force-categorized. Concerts are category `classical`; the
    section/cicle label goes to annotations. Date+time come from the card's class
    tokens; `prices` (optional) maps source_url -> price free text fetched from the
    detail page."""
    soup = BeautifulSoup(html, "html.parser")
    prices = prices or {}

    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for card in soup.select(".activitat"):
        if not _is_concert(card):
            continue

        link = card.select_one("a.link[href]")
        title_el = card.select_one(".title")
        title = _clean(title_el.get_text(" ")) if title_el else ""
        href = link.get("href", "").strip() if link else ""
        if not title or not href:
            continue

        start_date = _card_date(card)
        if start_date is None:
            continue  # no reliable date; skip rather than guess
        start_time = _card_time(card)

        source_url = _absolutize(href.split("?")[0].rstrip("/") + "/")

        # external_id unique per OCCURRENCE: the activity slug qualified by the
        # occurrence's date+time (the upsert dedups on (venue, external_id)).
        slug = _slug_from_url(source_url)
        time_part = start_time.strftime("%H%M") if start_time else "0000"
        external_id = f"{slug}@{start_date.isoformat()}T{time_part}"
        if external_id in seen:
            continue
        seen.add(external_id)

        annotations: list[str] = []
        # Section / cicle label (e.g. "Música") — a sub-label, never a category.
        chip = card.select_one(".e-chip")
        if chip:
            label = _clean(chip.get_text())
            if label:
                annotations.append(label)
        cicle = card.select_one(".cicle")
        if cicle:
            label = _clean(cicle.get_text())
            if label and label not in annotations:
                annotations.append(label)

        img = card.select_one(".wrap-img img[src]")
        image_url = _absolutize(img["src"].strip()) if img else None

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=source_url,
                category_slugs=["classical"],
                price=prices.get(source_url),
                image_url=image_url,
                external_id=external_id,
                annotations=annotations,
            )
        )

    return events


def parse_price(detail_html: str) -> str | None:
    """Public (non-member) ticket price from a concert detail page.

    Reads `p.price.nosocis` ("No socis — 20€") and returns a concise display string
    ("20€"). Member price (`p.price.socis`) is skipped per the price convention.
    Free phrases normalize to "free", sold-out phrases to "sold-out". None if no
    price block is present."""
    soup = BeautifulSoup(detail_html, "html.parser")
    el = soup.select_one("p.price.nosocis") or soup.select_one("p.price")
    if el is None:
        return None
    raw = _clean(el.get_text(" "))
    low = raw.lower()
    if any(p in low for p in _SOLD_OUT_PHRASES):
        return "sold-out"
    m = _PRICE_EUR.search(raw)
    if m:
        amount = m.group(1).rstrip("0").rstrip(".,") if "," in m.group(1) or "." in m.group(1) else m.group(1)
        return f"{amount}€"
    if any(p in low for p in _FREE_PHRASES):
        return "free"
    return None


class AteneuBarcelonesScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with httpx.Client(follow_redirects=True, timeout=30, headers=_HEADERS) as client:
            html = client.get(AGENDA_URL).text
            # First pass: identify the concert cards (and their detail URLs).
            stub_events = parse_agenda(html)
            # Fetch each concert's detail page once for the public price.
            prices: dict[str, str | None] = {}
            for ev in stub_events:
                if ev.source_url in prices:
                    continue
                try:
                    detail = client.get(ev.source_url).text
                except httpx.HTTPError:
                    continue
                prices[ev.source_url] = parse_price(detail)
            return parse_agenda(html, prices=prices)


register(
    scraper=AteneuBarcelonesScraper(),
    venue=VenueDefinition(
        slug="ateneu-barcelones",
        name="Ateneu Barcelonès",
        city_slug="barcelona",
        address="Carrer de la Canuda, 6, 08002 Barcelona",
        site_url="https://www.ateneubarcelones.cat",
        category_slugs=["classical"],
        list_memberships=[
            ListMembership(list_slug="classical"),
        ],
    ),
)
