from __future__ import annotations
import datetime as dt
import html as html_module
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Sala Phenomena Experience is an independent single-screen repertory cinema. Its
# full programme server-renders every film as a `div.cartelera` carrying the
# title, detail link, image, optional thematic *ciclo*, and every upcoming session
# (a date + one or more showtimes). One ScrapedEvent is emitted per SESSION (the
# venue's `id-ses` is a native per-occurrence id). The listing carries no price —
# each film's price lives on its ficha detail page (`.precio`), fetched once per
# film and applied to all its sessions. See phenomena_SOURCE.md.
CARTELERA_URL = "https://phenomena-experience.com/index?pag=cartelera"
BASE_URL = "https://phenomena-experience.com"
VENUE_SLUG = "phenomena"

_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_TIME = re.compile(r"(\d{1,2}):(\d{2})")
_EVENTO = re.compile(r"evento=(\d+)")
_PRICE = re.compile(r"(\d+(?:[.,]\d+)?)\s*€")


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").strip()


def _absolutize(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE_URL + url
    return url


def _film_title(block: Tag) -> str | None:
    el = block.select_one(".cartelera-titulo .ver-ficha")
    return _clean(el.get_text(" ", strip=True)) if el else None


def _film_url(block: Tag) -> str | None:
    a = block.select_one(".cartelera-imagen a[href*=ficha]")
    href = a.get("href") if a else None
    return _absolutize(href) if href else None


def _film_image(block: Tag) -> str | None:
    img = block.select_one(".cartelera-imagen img[src]")
    src = img.get("src") if img else None
    return _absolutize(src) if src else None


def _film_cycle(block: Tag) -> str | None:
    """The thematic *ciclo* (e.g. "Ciclo: SPIELBERG FANTÁSTICO" → "SPIELBERG FANTÁSTICO")."""
    el = block.select_one(".cartelera-titulo-ciclo span")
    if not el:
        return None
    text = _clean(el.get_text(" ", strip=True))
    text = re.sub(r"^ciclo:\s*", "", text, flags=re.IGNORECASE)
    return text or None


def _film_description(block: Tag) -> str | None:
    """Original/alt title (2nd `.ver-ficha`) plus the runtime/director/cast lines."""
    parts: list[str] = []
    titles = block.select(".cartelera-titulo .ver-ficha")
    if len(titles) > 1:
        alt = _clean(titles[1].get_text(" ", strip=True))
        if alt:
            parts.append(alt)
    info = block.select_one(".cartelera-informacion")
    if info:
        text = _clean(info.get_text(" ", strip=True))
        if text:
            parts.append(text)
    return " — ".join(parts) if parts else None


def _parse_date(text: str) -> dt.date | None:
    m = _DATE.search(text)
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _parse_time(text: str) -> dt.time | None:
    m = _TIME.search(text)
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    return dt.time(hh, mm) if 0 <= hh < 24 and 0 <= mm < 60 else None


def _film_sessions(block: Tag) -> list[tuple[dt.date, dt.time | None, str | None]]:
    """(date, time, id-ses) for every `.grupo` session under this film.

    `.fch-format` (a date) is immediately followed by a sibling `.sesiones-dia`
    whose `.grupo[id-ses]` children each hold one showtime."""
    sessions: list[tuple[dt.date, dt.time | None, str | None]] = []
    for fch in block.select(".lista-sesiones .fch-format"):
        date = _parse_date(fch.get_text(strip=True))
        if date is None:
            continue
        day = fch.find_next_sibling("div", class_="sesiones-dia")
        if not day:
            continue
        for grupo in day.select(".grupo"):
            tdiv = grupo.select_one("div")
            time = _parse_time(tdiv.get_text(strip=True)) if tdiv else None
            id_ses = grupo.get("id-ses") or None
            sessions.append((date, time, id_ses))
    return sessions


def parse_price(html: str) -> str | None:
    """The film's public ticket price from its ficha detail page (`.precio`)."""
    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one(".precio")
    if not el:
        return None
    m = _PRICE.search(el.get_text(" ", strip=True))
    if not m:
        return None
    amount = m.group(1).replace(".", ",")
    return f"{amount}€"


def parse_cartelera(
    html: str, prices: dict[str, str | None] | None = None
) -> list[ScrapedEvent]:
    """Parse the Phenomena full-programme page into one ScrapedEvent per session.

    Each `div.cartelera` is one film with 1+ sessions; we emit a ScrapedEvent per
    session keyed by the venue's `id-ses` (unique per occurrence). Every session is
    category `film`. `prices` maps a film's `evento` id → its price string (read
    from the ficha detail page); applied to all of that film's sessions."""
    soup = BeautifulSoup(html, "html.parser")
    prices = prices or {}

    events: list[ScrapedEvent] = []
    for block in soup.select("div.cartelera"):
        title = _film_title(block)
        source_url = _film_url(block)
        if not title or not source_url:
            continue

        m = _EVENTO.search(source_url)
        evento = m.group(1) if m else None
        price = prices.get(evento) if evento else None

        image_url = _film_image(block)
        cycle = _film_cycle(block)
        description = _film_description(block)
        annotations = [cycle] if cycle else []

        for date, time, id_ses in _film_sessions(block):
            # external_id is the venue's native per-session id (unique per
            # occurrence). Fall back to evento+date+time only if id-ses is missing,
            # so repeat screenings of one film never collapse onto one row.
            if id_ses:
                external_id = id_ses
            else:
                time_part = time.strftime("%H%M") if time else "0000"
                external_id = (
                    f"{evento}@{date.isoformat()}T{time_part}" if evento else None
                )

            events.append(
                ScrapedEvent(
                    title=title,
                    start_date=date,
                    start_time=time,
                    source_url=source_url,
                    category_slugs=["film"],
                    price=price,
                    description=description,
                    image_url=image_url,
                    external_id=external_id,
                    annotations=list(annotations),
                )
            )

    return events


def _evento_ids(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    ids: list[str] = []
    for a in soup.select(".cartelera-imagen a[href*=ficha]"):
        m = _EVENTO.search(a.get("href", ""))
        if m and m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


class PhenomenaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            html = client.get(CARTELERA_URL).text
            # Price lives per-film on the ficha detail page; fetch each once.
            prices: dict[str, str | None] = {}
            for evento in _evento_ids(html):
                try:
                    ficha = client.get(
                        BASE_URL + "/index", params={"pag": "ficha", "evento": evento}
                    ).text
                    prices[evento] = parse_price(ficha)
                except httpx.HTTPError:
                    prices[evento] = None
            return parse_cartelera(html, prices=prices)


register(
    scraper=PhenomenaScraper(),
    venue=VenueDefinition(
        slug="phenomena",
        name="Phenomena Experience",
        city_slug="barcelona",
        address="Carrer de Sant Antoni Maria Claret, 168, Horta-Guinardó, 08025 Barcelona",
        site_url="https://phenomena-experience.com",
        category_slugs=["film"],
        list_memberships=[
            ListMembership(list_slug="film"),
        ],
    ),
)
