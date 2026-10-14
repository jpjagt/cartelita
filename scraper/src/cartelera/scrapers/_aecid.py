"""Shared scraper for the Spanish Cooperation (AECID) cultural centres' sites.

The Centros Culturales de España run one Liferay platform at
`https://<centre>.aecid.es` (Asunción, Montevideo, Lima, Guatemala,
Tegucigalpa, Santiago … — same templates). Its event agenda:

- `/eventos/buscador-de-eventos` carries the agenda portlet; its container's
  `data-listado-url` attribute is a JSON resource URL (portlet instance id
  differs per site). `GET <listado-url>&<ns>keywords=&<ns>start=N&<ns>from=
  YYYY-MM-DD&<ns>to=&<ns>sort=asc` (`<ns>` = `_<p_p_id>_`) returns
  `{totalHits, size: 12, documents: [{articleId, title, html}]}`; each `html`
  is a card: title link (`a.title` → `/w/<slug>`), image, all dates
  (`.fechas-repetibles`) and the agenda's category labels (`.cat-reco`).
  `from` keeps every item with a date on/after it (incl. its past dates).
- An item's detail page (`/w/<slug>`): `h1` title, `h2.tit-h4` subtitle,
  `.col-content` body, `.col-izq img` image, and a `.col-der dl` of
  structured fields — Categoría (`span.estado`), Fecha (one
  `.fecha-repetible-item` per date, hidden ones included), Horario (free text,
  optional: "19.30 horas.", "18.00 a 20.00 horas.", "Según programación."),
  Lugar (free text).

One item is a programme entry that may span many dates; we emit one row per
date (and per stated time on that date). Times: the Horario field, else times
the body states next to that date ("miércoles 28 de octubre, 19:30 horas").

Private module (leading underscore): skipped by `load_all()`. A centre's
module supplies its category mapping and place markers via `AecidConfig`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.scrapers.price import pyg_price
from cartelera.types import ScrapedEvent

SEARCH_PATH = "/eventos/buscador-de-eventos"
_MAX_PAGES = 30

MONTHS = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}
MONTH_NAMES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre",
    12: "diciembre",
}
_DATE = re.compile(r"(\d{1,2})/([A-Za-zé]{3})/(\d{4})")
_TIME = r"(\d{1,2})[:.](\d{2})\s*(?:h\b|hs\b|horas\b|hrs\b)"
_FREE = re.compile(
    r"\b(?:acceso|entrada|ingreso)s?\s+(?:libre|gratuit[oa])|libre\s+y\s+gratuit[oa]",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AecidConfig:
    site: str                                  # "https://cceasuncion.aecid.es"
    venue_slug: str
    programme: dict[str, str]                  # agenda category label -> our category
    non_programme: frozenset[str] = frozenset()  # labels that veto an item
    extra: dict[str, str] = field(default_factory=dict)  # label -> added category
    # Lugar must mention one of these (case-insensitive) — or be empty.
    own_place_markers: tuple[str, ...] = ()


@dataclass
class Detail:
    title: str
    subtitle: str
    categories: list[str]
    dates: list[dt.date]
    horario: str
    lugar: str
    body: str
    image_url: str | None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def parse_date(text: str) -> dt.date | None:
    m = _DATE.search(text)
    if not m:
        return None
    month = MONTHS.get(m.group(2).lower()[:3])
    if not month:
        return None
    return dt.date(int(m.group(3)), month, int(m.group(1)))


# --- listing ------------------------------------------------------------------


def listing_endpoint(search_html: str) -> tuple[str, str]:
    """(JSON listing URL, parameter namespace) from the search page."""
    soup = BeautifulSoup(search_html, "html.parser")
    el = soup.select_one("[data-listado-url]")
    if el is None:
        raise ValueError("AECID agenda: no data-listado-url on the search page")
    url = el["data-listado-url"].replace(":443/", "/")
    portlet = parse_qs(urlparse(url).query)["p_p_id"][0]
    return url, f"_{portlet}_"


def listing_page_url(endpoint: str, ns: str, start: int, date_from: dt.date) -> str:
    params = {
        f"{ns}keywords": "",
        f"{ns}start": str(start),
        f"{ns}from": date_from.isoformat(),
        f"{ns}to": "",
        f"{ns}sort": "asc",
    }
    return f"{endpoint}&{urlencode(params)}"


def parse_listing(payload: dict, site: str) -> list[dict]:
    """Cards → {article_id, url, title, categories, image_url}."""
    items = []
    for doc in payload.get("documents") or []:
        soup = BeautifulSoup(doc.get("html") or "", "html.parser")
        link = soup.select_one("a.title[href]")
        if link is None:
            continue
        img = soup.select_one("img[src]")
        items.append({
            "article_id": str(doc.get("articleId") or ""),
            "url": urljoin(site, link["href"]),
            "title": _clean(doc.get("title") or link.get_text(" ")),
            "categories": [_clean(a.get_text(" ")) for a in soup.select(".cat-reco")],
            "image_url": urljoin(site, img["src"]) if img else None,
        })
    return items


def fetch_listing(site: str, date_from: dt.date) -> list[dict]:
    headers = CARTELITA_BROWSER_HEADERS
    endpoint, ns = listing_endpoint(fetch(site + SEARCH_PATH, headers=headers))
    items: list[dict] = []
    start = 0
    for _ in range(_MAX_PAGES):
        payload = json.loads(fetch(listing_page_url(endpoint, ns, start, date_from), headers=headers))
        page = parse_listing(payload, site)
        items.extend(page)
        start += int(payload.get("size") or 12)
        if not page or start >= int(payload.get("totalHits") or 0):
            break
    return items


# --- detail -------------------------------------------------------------------


def _field(dl: Tag, name: str) -> list[Tag]:
    """The `dd`s following the `dt` called `name` (a field with several
    values — e.g. two category labels — has one `dd` per value)."""
    for dt_el in dl.find_all("dt"):
        if _clean(dt_el.get_text(" ")).lower() != name.lower():
            continue
        out: list[Tag] = []
        for sib in dt_el.find_next_siblings():
            if sib.name != "dd":
                break
            out.append(sib)
        return out
    return []


def _joined(dds: list[Tag]) -> str:
    return _clean(" ".join(d.get_text(" ") for d in dds))


def parse_detail(html: str, site: str) -> Detail:
    soup = BeautifulSoup(html, "html.parser")
    dl = soup.select_one(".col-der dl") or soup
    cat_dd = _field(dl, "Categoría")
    date_dd = _field(dl, "Fecha")
    hor_dd = _field(dl, "Horario")
    lug_dd = _field(dl, "Lugar")
    dates: list[dt.date] = []
    for item in (i for d in date_dd for i in d.select(".fecha-repetible-item")):
        d = parse_date(item.get_text(" "))
        if d and d not in dates:
            dates.append(d)
    body_el = soup.select_one(".col-content")
    img = soup.select_one(".col-izq img[src]")
    h1 = soup.select_one(".col-izq h1") or soup.select_one("h1")
    h2 = soup.select_one(".col-izq h2")
    return Detail(
        title=_clean(h1.get_text(" ")) if h1 else "",
        subtitle=_clean(h2.get_text(" ")) if h2 else "",
        categories=[_clean(sp.get_text(" ")) for d in cat_dd for sp in d.select("span")],
        dates=dates,
        horario=_joined(hor_dd),
        lugar=_joined(lug_dd),
        body=_clean(body_el.get_text(" ")) if body_el else "",
        image_url=urljoin(site, img["src"]) if img else None,
    )


def times_for(detail: Detail, day: dt.date) -> list[dt.time]:
    """Start times on `day`: the Horario field's start (the first time it
    states — "18.00 a 20.00 horas" starts at 18:00), else every time the body
    states right after this date ("… 28 de octubre, 19:30 horas")."""
    # The Horario value states the unit once at the end ("18.00 a 20.00
    # horas."), so read its first clock time.
    first = re.search(r"(\d{1,2})[:.](\d{2})", detail.horario or "")
    if first and 0 <= int(first.group(1)) < 24 and 0 <= int(first.group(2)) < 60:
        return [dt.time(int(first.group(1)), int(first.group(2)))]
    anchor = rf"\b{day.day}\s+de\s+{MONTH_NAMES[day.month]}\b[^.\n]{{0,40}}?" + _TIME
    found: list[dt.time] = []
    for m in re.finditer(anchor, detail.body, re.IGNORECASE):
        hh, mm = int(m.group(1)), int(m.group(2))
        if 0 <= hh < 24 and 0 <= mm < 60 and dt.time(hh, mm) not in found:
            found.append(dt.time(hh, mm))
    return sorted(found)


def price(body: str) -> str | None:
    """A stated guaraní price, else "free" for "acceso libre y gratuito"."""
    stated = pyg_price(body)
    if stated:
        return stated
    if _FREE.search(body):
        return "free"
    return None


def categorize(labels: list[str], cfg: AecidConfig) -> list[str]:
    if set(labels) & cfg.non_programme:
        return []
    cats = list(dict.fromkeys(cfg.programme[l] for l in labels if l in cfg.programme))
    if cats:
        cats += [c for l, c in cfg.extra.items() if l in labels and c not in cats]
    return cats


def at_own_place(lugar: str, cfg: AecidConfig) -> bool:
    if not lugar or not cfg.own_place_markers:
        return True
    low = lugar.lower()
    return any(m.lower() in low for m in cfg.own_place_markers)


def events_from_detail(
    detail: Detail, item: dict, cfg: AecidConfig, today: dt.date
) -> list[ScrapedEvent]:
    """One ScrapedEvent per (date, start time) from today on — or none when
    the item isn't programme or takes place elsewhere."""
    labels = detail.categories or item.get("categories") or []
    cats = categorize(labels, cfg)
    if not cats or not at_own_place(detail.lugar, cfg):
        return []
    title = detail.title or item.get("title") or ""
    if not title:
        return []
    annotations = [l for l in labels if l not in cfg.programme and l not in cfg.extra]
    if detail.subtitle:
        annotations.append(detail.subtitle)
    description = detail.body[:2000] or None
    event_price = price(detail.body)
    key = item.get("article_id") or urlparse(item["url"]).path.rstrip("/").rsplit("/", 1)[-1]
    events: list[ScrapedEvent] = []
    for day in detail.dates:
        if day < today:
            continue
        for t in times_for(detail, day) or [None]:
            hhmm = t.strftime("%H%M") if t else "0000"
            events.append(
                ScrapedEvent(
                    title=title,
                    start_date=day,
                    start_time=t,
                    source_url=item["url"],
                    category_slugs=list(cats),
                    price=event_price,
                    description=description,
                    image_url=detail.image_url or item.get("image_url"),
                    external_id=f"{key}@{day.isoformat()}T{hhmm}",
                    annotations=list(annotations),
                )
            )
    return events


def scrape(cfg: AecidConfig, today: dt.date) -> list[ScrapedEvent]:
    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for item in fetch_listing(cfg.site, today):
        # The card carries the same labels as the detail: skip non-programme
        # items without fetching them.
        if not categorize(item["categories"], cfg):
            continue
        detail = parse_detail(fetch(item["url"], headers=CARTELITA_BROWSER_HEADERS), cfg.site)
        for ev in events_from_detail(detail, item, cfg, today):
            if ev.external_id not in seen:
                seen.add(ev.external_id)
                events.append(ev)
    return events
