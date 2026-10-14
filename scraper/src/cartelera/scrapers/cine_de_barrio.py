"""Cine de Barrio (Barrio Las Mercedes, Asunción) — a 20-seat auteur cinema.

Own site: a Framer site, fully server-rendered. `/eventos` lists one card per
film (`a[href^="./eventos/<slug>"]`: title, optional genre label, poster);
each film's detail page lists its screenings ("Funciones"), one block per
showtime with a `<time datetime>`, a price ("40.000 PYG") and a ticket link
to a Tally form carrying the screening's own Airtable record id
(`screening_id=rec…`) — our per-occurrence external_id.

Framer renders the page once per breakpoint, so every field appears twice;
blocks are deduped by screening id. See cine_de_barrio_SOURCE.md.
"""

from __future__ import annotations

import datetime as dt
import re
from urllib.parse import parse_qs, quote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.scrapers.price import pyg_price
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

BASE_URL = "https://cinedebarrio.com"
LIST_URL = f"{BASE_URL}/eventos"
VENUE_SLUG = "cine-de-barrio"

_FREE = re.compile(r"\b(gratis|gratuit[oa]|entrada libre|acceso libre)\b", re.IGNORECASE)
_SOLD_OUT = re.compile(r"\bagotad[oa]s?\b|sold.?out", re.IGNORECASE)


def _text(el: Tag | None) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _field(root: Tag, name: str) -> Tag | None:
    return root.select_one(f'[data-framer-name="{name}"]')


def _abs_url(href: str) -> str:
    """'./eventos/el-príncipe-de-nanawa' → percent-encoded absolute URL (the
    form the site's own og:url uses)."""
    url = urljoin(BASE_URL + "/", href)
    parts = urlparse(url)
    return parts._replace(path=quote(parts.path, safe="/%")).geturl()


def parse_list(html: str) -> list[dict]:
    """One dict per film card: url, title, genre (may be ''), image_url."""
    soup = BeautifulSoup(html, "html.parser")
    films: dict[str, dict] = {}
    for a in soup.select('a[href*="eventos/"]'):
        url = _abs_url(a["href"])
        if url in films:
            continue
        img = a.select_one("img[src]")
        films[url] = {
            "url": url,
            "title": _text(_field(a, "Titulo")),
            "genre": _text(_field(a, "Genero")),
            "image_url": img["src"] if img else None,
        }
    return list(films.values())


def _price(text: str) -> str | None:
    if _SOLD_OUT.search(text):
        return "sold-out"
    price = pyg_price(text)
    if price:
        return price
    if _FREE.search(text):
        return "free"
    return None


def _screening_id(link: Tag | None) -> str | None:
    if link is None:
        return None
    ids = parse_qs(urlparse(link["href"]).query).get("screening_id")
    return ids[0] if ids else None


def parse_detail(html: str, film: dict) -> list[ScrapedEvent]:
    """One ScrapedEvent per screening on a film's detail page."""
    soup = BeautifulSoup(html, "html.parser")
    info = _field(soup, "info") or soup
    title = _text(_field(info, "Titulo")) or film.get("title") or ""
    if not title:
        return []
    description = _text(_field(info, "Descripcion")) or None
    annotations = [film["genre"]] if film.get("genre") else []
    slug = film["url"].rstrip("/").rsplit("/", 1)[-1]

    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for block in soup.select('[data-framer-name="Fecha y Hora"]'):
        time_el = block.select_one("time[datetime]")
        if time_el is None:
            continue
        # Framer stores the wall-clock showtime with a "Z" suffix: the
        # rendered text ("14 oct 2026, 19:00") is the same clock time, so the
        # value is local Asunción time, not UTC.
        when = dt.datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
        start_date, start_time = when.date(), when.time().replace(tzinfo=None)
        # One showtime's card: its date, then a Precio field + Tally ticket
        # link (paid), or a note like "Entrada libre y gratuita" (free).
        card = block.find_parent(attrs={"data-border": "true"}) or block.parent
        price_el = card.select_one('[data-framer-name="Precio"]')
        link = card.find("a", href=re.compile(r"screening_id="))
        sid = _screening_id(link)
        external_id = sid or f"{slug}@{start_date.isoformat()}T{start_time:%H%M}"
        if external_id in seen:
            continue
        seen.add(external_id)
        notes = [_text(s) for s in card.select("section")]
        price_text = " ".join(filter(None, [_text(price_el), *notes]))
        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=film["url"],
                category_slugs=["film"],
                price=_price(price_text),
                description=description,
                image_url=film.get("image_url"),
                external_id=external_id,
                annotations=list(annotations),
            )
        )
    return events


class CineDeBarrioScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        headers = CARTELITA_BROWSER_HEADERS
        events: list[ScrapedEvent] = []
        seen: set[str] = set()
        for film in parse_list(fetch(LIST_URL, headers=headers)):
            for ev in parse_detail(fetch(film["url"], headers=headers), film):
                if ev.external_id not in seen:
                    seen.add(ev.external_id)
                    events.append(ev)
        return events


register(
    scraper=CineDeBarrioScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Cine de Barrio",
        city_slug="asuncion",
        address="Defensa Nacional 737 casi Washington, Asunción",
        site_url=BASE_URL,
        instagram_url="https://www.instagram.com/cinedebarriopy",
        category_slugs=["film"],
        list_memberships=[ListMembership(list_slug="film", whitelist_category_slug="film")],
    ),
)
