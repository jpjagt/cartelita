"""TivoliVredenburg (Utrecht) — the city's main music venue.

A WordPress site. The agenda (`/agenda/`, `/agenda/page/N/`, 20 cards a page,
~40+ pages) is server-rendered; each card carries the title, detail URL, date
and the event's genre term slugs (`button[data-genre]`). The genre filter menu
on the same page gives the term hierarchy (top-level group → sub-genres), which
is the category discriminator. Time, hall, price and status live only on the
detail page (`/agenda/<id>/<slug>-<dd-mm-yyyy>`): a `<dl class=
"description-list">` with "Deuren open"/"Aanvang"/"Start"/"Verwachte eindtijd"
times, price tiers, and "Locatie"; plus a JSON-LD MusicEvent (whose startDate is
the DOORS time — not used for the start). See tivolivredenburg_SOURCE.md.

Curation (the owner's brief: the artistic programme, not every booking) is done
on the venue's own labels, never on title keywords:
- genre group → category (pop-rock→pop, klassiek→classical, jazz→jazz,
  dance-by-night→club, global→folk, familie→kids); items with no music genre
  (empty, or only "Kennis & Debat"/"Comedy") are left out;
- events located outside the building (another venue: dB's, De Helling,
  UJazz's Buitenwereld, churches, libraries) are left out — they belong to
  those venues;
- the venue's non-programme series (De Vrije Ruimte community activities,
  schoolconcerten, podcasts, the Park 6 hangout bar) are left out;
- cancelled ("Afgelast") and moved ("Verplaatst") items are left out.
"""
from __future__ import annotations

import datetime as dt
import html as html_module
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

logger = logging.getLogger(__name__)

BASE_URL = "https://www.tivolivredenburg.nl"
AGENDA_URL = BASE_URL + "/agenda/"
VENUE_SLUG = "tivolivredenburg"
USER_AGENT = "Cartelita (+https://cartelita.july.dev)"
MAX_PAGES = 80
MAX_CONCURRENCY = 2
PAGE_DELAY = 0.5  # seconds between requests per worker — be polite

# Top-level genre group (the agenda filter's parent terms) → our category.
GROUP_CATEGORY = {
    "pop-rock": "pop",
    "klassiek": "classical",
    "jazz": "jazz",
    "dance-by-night": "club",
    "global": "folk",
    "familie": "kids",
}
# Groups that are not music programme on their own (talks, stand-up comedy).
# They never yield a category; an event tagged ONLY with these is left out.
NON_MUSIC_GROUPS = {"kennis-debat", "comedy"}
# Family concerts go to `kids` only — not also to the adult music lists.
EXCLUSIVE_GROUPS = {"familie": "kids"}

# Spaces inside the building, as the detail page's "Locatie" names them.
# A location linking to tivolivredenburg.nl is in-house too (new halls).
IN_HOUSE_SPACES = {
    "grote zaal", "hertz", "cloud nine", "ronda", "pandora", "club nine",
    "park 6", "rabo open stage", "vredenburg open stage", "tivolivredenburg",
    "omloop grote zaal", "omloop ronda", "gehele gebouw", "van vlissingen foyer",
    "k.f. hein foyer", "pandora foyer", "punt laag 6", "studio pandora",
}

# Non-programme series, by the path of the detail page's series link
# (`.event-collection-cta a[href]`).
EXCLUDED_SERIES_PATHS = (
    "/de-vrije-ruimte",          # community activities: yoga, linedance, gaming…
    "/connect/schoolconcerten",  # school concerts (classes, not the public)
    "/studio/podcast",           # podcast recordings
    "/park6",                    # the free foyer hangout bar (DJs, games)
)

# Price-tier labels that are discounts or upsell packages, not the public price.
_NON_PUBLIC_TIER = re.compile(
    r"onder 30|kind|u-pas|student|jongere|groep|duo|gezin|ouder|vip|meet|"
    r"package|experience|early entry",
    re.IGNORECASE,
)
_AMOUNT = re.compile(r"€\s*(\d+)(?:,(\d{2}|-))?")
_TIME = re.compile(r"\b(\d{1,2})[:.](\d{2})\b")
_LIST_DATE = re.compile(r"(\d{1,2})\s+([a-z]{3})\w*\.?\s+(\d{4})", re.IGNORECASE)
_MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


@dataclass
class ListItem:
    """One agenda card."""
    external_id: str
    url: str
    title: str
    genres: list[str]
    date: dt.date | None
    image_url: str | None = None
    free: bool = False


@dataclass
class Detail:
    """What the detail page adds to a card."""
    start_times: list[dt.time] = field(default_factory=list)
    doors: dt.time | None = None
    end_time: dt.time | None = None
    ld_start: dt.datetime | None = None
    location: str | None = None
    in_house: bool = True
    price: str | None = None
    sold_out: bool = False
    free: bool = False
    badges: list[str] = field(default_factory=list)
    series_paths: list[str] = field(default_factory=list)
    subtitle: str | None = None
    image_url: str | None = None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html_module.unescape(text).replace("\xa0", " ")).strip()


# --- list page -------------------------------------------------------------

def parse_genre_tree(html: str) -> dict[str, tuple[str, str]]:
    """Genre term slug → (top-level group slug, human label), from the agenda's
    genre filter menu. Sub-terms are keyed by both their `data-term_id` and
    their `?sf_genre=` slug (the cards' `data-genre` uses the latter)."""
    soup = BeautifulSoup(html, "html.parser")
    tree: dict[str, tuple[str, str]] = {}
    root = soup.select_one(".filter-categories") or soup
    for top in root.select("div.filter--genre"):
        head = top.find("a", attrs={"data-taxonomy": "genre"})
        if head is None or not head.get("data-term_id"):
            continue
        group = head["data-term_id"]
        tree[group] = (group, _clean(head.get_text(" ")))
        for a in top.select("ul.filter-subitems a[data-taxonomy=genre]"):
            label = _clean(a.get_text(" "))
            keys = {a.get("data-term_id")}
            qs = parse_qs(urlparse(a.get("href", "")).query)
            keys.update(qs.get("sf_genre", []))
            for k in keys:
                if k:
                    tree[k] = (group, label)
    return tree


def _parse_list_date(text: str) -> dt.date | None:
    m = _LIST_DATE.search(text)
    if not m or m.group(2).lower() not in _MONTHS:
        return None
    try:
        return dt.date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
    except ValueError:
        return None


def parse_list(html: str) -> list[ListItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[ListItem] = []
    for li in soup.select("li.agenda-list-item"):
        a = li.select_one("a.agenda-list-item__title-link[href]")
        if a is None:
            continue
        url = a["href"]
        m = re.search(r"/agenda/(\d+)/", url)
        if not m:
            continue
        btn = li.select_one("[data-genre]")
        genres = [g.strip() for g in (btn["data-genre"] if btn else "").split(",") if g.strip()]
        when = li.select_one("time.agenda-list-item__time")
        img = li.select_one("img[src]")
        ticket = li.select_one("a.agenda-list-item__link")
        items.append(ListItem(
            external_id=m.group(1),
            url=url,
            title=_clean(a.get_text(" ")),
            genres=genres,
            date=_parse_list_date(when.get_text(" ")) if when else None,
            image_url=img["src"] if img else None,
            free=bool(ticket and _clean(ticket.get_text(" ")).lower() == "gratis"),
        ))
    return items


def has_next_page(html: str, page: int) -> bool:
    return f"/agenda/page/{page + 1}/" in html


# --- curation --------------------------------------------------------------

def categorize(genres: list[str], tree: dict[str, tuple[str, str]]) -> tuple[list[str], list[str]]:
    """(category slugs, sub-genre labels for annotations) from a card's genre
    slugs. Empty categories ⇒ not music programme (leave the event out)."""
    groups: list[str] = []
    labels: list[str] = []
    for g in genres:
        group, label = tree.get(g, (None, None))
        if group is None:
            continue
        if group not in groups:
            groups.append(group)
        if g != group and label and label not in labels:
            labels.append(label)
    for group, cat in EXCLUSIVE_GROUPS.items():
        if group in groups:
            return [cat], labels
    # Stable order (the card's term order varies): GROUP_CATEGORY's order.
    cats = [cat for group, cat in GROUP_CATEGORY.items() if group in groups]
    return cats, labels


def exclusion_reason(item: ListItem, detail: Detail | None, tree) -> str | None:
    """Why an agenda item is not part of the curated programme, or None."""
    cats, _ = categorize(item.genres, tree)
    if not cats:
        return "no music genre" if item.genres else "no genre (non-programme)"
    if detail is None:
        return None
    if any(b.lower() in ("afgelast", "verplaatst") for b in detail.badges):
        return "cancelled/moved"
    if not detail.in_house:
        return f"off-site ({detail.location})"
    for path in detail.series_paths:
        if path.startswith(EXCLUDED_SERIES_PATHS):
            return f"non-programme series ({path})"
    return None


# --- detail page -----------------------------------------------------------

def _time(text: str) -> dt.time | None:
    m = _TIME.search(text)
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    return dt.time(hh, mm) if hh < 24 and mm < 60 else None


def _fmt_amount(cents: int) -> str:
    euros, rest = divmod(cents, 100)
    return f"{euros}€" if rest == 0 else f"{euros},{rest:02d}€"


def _cents(text: str) -> int | None:
    m = _AMOUNT.search(text)
    if not m:
        return None
    frac = m.group(2)
    return int(m.group(1)) * 100 + (int(frac) if frac and frac != "-" else 0)


def _format_tiers(cents: list[int]) -> str:
    lo, hi = min(cents), max(cents)
    if hi == 0:
        return "free"
    # The skill's 2x rule: a range only for a meaningful spread.
    if lo > 0 and lo != hi and hi >= 2 * lo:
        return f"{_fmt_amount(lo)[:-1]}–{_fmt_amount(hi)}"
    return _fmt_amount(hi)


def _location_in_house(dd: Tag) -> tuple[str, bool]:
    name = _clean(dd.get_text(" "))
    for a in dd.find_all("a", href=True):
        if "tivolivredenburg.nl" in a["href"]:
            return name, True
    parts = [p.strip().lower() for p in name.split(",") if p.strip()]
    return name, bool(parts) and any(p in IN_HOUSE_SPACES for p in parts)


def parse_detail(html: str) -> Detail:
    soup = BeautifulSoup(html, "html.parser")
    d = Detail()
    info = soup.select_one(".event__info dl.description-list")
    starts: list[dt.time] = []
    act_times: list[dt.time] = []
    programme_text = ""
    if info is not None:
        for dt_el in info.find_all("dt", recursive=False):
            low = _clean(dt_el.get_text(" ")).lower()
            # Time rows render <dd><time>value</time></dd><dt>label</dt>
            # (value first); every other row is <dt>label</dt><dd>value</dd>.
            prev_dd = dt_el.find_previous_sibling()
            if prev_dd is not None and prev_dd.name == "dd" and prev_dd.find("time", recursive=False):
                t = _time(prev_dd.get_text(" "))
                if t is None:
                    continue
                if low.startswith("deuren open"):
                    d.doors = d.doors or t
                elif "aanvang" in low or low.startswith("start"):
                    starts.append(t)
                elif "eindtijd" in low:
                    d.end_time = d.end_time or t
                elif low not in ("pauze",) and not low.startswith(("inleiding", "verzamel", "aankomst", "pack-up")):
                    # Per-act set times ("Amber Run 19:45", "Freya Ridings
                    # 20:45"): the first act opens the show.
                    act_times.append(t)
                continue
            dd = dt_el.find_next_sibling("dd")
            if dd is None:
                continue
            if low == "locatie":
                d.location, d.in_house = _location_in_house(dd)
            elif low.startswith("programma"):
                programme_text += " " + _clean(dd.get_text(" "))
    if not starts and programme_text:
        # Family shows list their sessions in prose: "Aanvang: 10.00 uur".
        for m in re.finditer(r"Aanvang\s*:?\s*(\d{1,2})[.:](\d{2})", programme_text):
            hh, mm = int(m.group(1)), int(m.group(2))
            if hh < 24 and mm < 60:
                starts.append(dt.time(hh, mm))
    d.start_times = sorted(set(starts)) or sorted(set(act_times))[:1]

    # Price tiers (seated halls: Rang 1/2/3 × Regulier/Onder 30 jaar; free
    # seating: Volwassene/Kind; pop shows: Early/Regular/Late Ticket).
    tier_cents: list[int] = []
    for tier in soup.select(".event__info dl.description-list--price"):
        label_el, value_el = tier.find("dt"), tier.find("dd")
        if not label_el or not value_el:
            continue
        if _NON_PUBLIC_TIER.search(_clean(label_el.get_text(" "))):
            continue
        c = _cents(value_el.get_text(" "))
        if c is not None:
            tier_cents.append(c)
    cta = soup.select_one(".event-cta")
    if cta is not None:
        d.badges = [_clean(b.get_text(" ")) for b in cta.select(".badge")]
        d.sold_out = any(
            (a.get("data-status") or "").lower() == "sold out"
            for a in cta.select(".btn-group__link")
        )
        sub = cta.select_one(".event__subtitle")
        d.subtitle = _clean(sub.get_text(" ")) or None if sub else None
    d.free = any(b.lower() == "gratis" for b in d.badges)
    if tier_cents:
        d.price = _format_tiers(tier_cents)
    elif cta is not None and (p := cta.select_one(".btn-group__price")) is not None:
        c = _cents(p.get_text(" "))
        if c is not None:
            # "v.a. € 48,-" without a tier table: the only figure we have.
            d.price = "free" if c == 0 else _fmt_amount(c)

    for a in soup.select(".event-collection-cta a[href]"):
        path = urlparse(a["href"]).path.rstrip("/")
        if path and path not in d.series_paths:
            d.series_paths.append(path)

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("@type") == "MusicEvent":
            try:
                d.ld_start = dt.datetime.fromisoformat(data.get("startDate", ""))
            except ValueError:
                pass
            d.image_url = data.get("image") or None
    return d


# --- assembly --------------------------------------------------------------

def build_event(item: ListItem, detail: Detail, tree) -> ScrapedEvent | None:
    if exclusion_reason(item, detail, tree):
        return None
    cats, labels = categorize(item.genres, tree)
    start_date = item.date or (detail.ld_start.date() if detail.ld_start else None)
    if start_date is None:
        return None
    starts = detail.start_times
    start_time = starts[0] if starts else detail.doors
    if start_time is None and detail.ld_start is not None:
        t = detail.ld_start.time()
        start_time = t if t != dt.time(0, 0) else None
    end_date = end_time = None
    if detail.end_time is not None and start_time is not None:
        end_time = detail.end_time
        end_date = start_date + dt.timedelta(days=1) if end_time <= start_time else start_date

    if detail.sold_out:
        price = "sold-out"
    elif item.free or detail.free:
        price = "free"
    else:
        price = detail.price

    annotations = list(labels)
    if detail.location:
        annotations.insert(0, detail.location)
    return ScrapedEvent(
        title=item.title,
        start_date=start_date,
        start_time=start_time,
        start_times=starts if len(starts) > 1 else [],
        end_date=end_date,
        end_time=end_time,
        source_url=item.url,
        category_slugs=cats,
        price=price,
        description=detail.subtitle,
        image_url=detail.image_url or item.image_url,
        external_id=item.external_id,
        annotations=annotations,
    )


class TivoliVredenburgScraper:
    venue_slug = VENUE_SLUG

    def _get(self, client: httpx.Client, url: str) -> str:
        resp = client.get(url)
        resp.raise_for_status()
        time.sleep(PAGE_DELAY)
        return resp.text

    def scrape(self) -> list[ScrapedEvent]:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30
        ) as client:
            first = self._get(client, AGENDA_URL)
            tree = parse_genre_tree(first)
            if not tree:
                raise RuntimeError("tivolivredenburg: genre filter menu not found")
            items = parse_list(first)
            page, html = 1, first
            while has_next_page(html, page) and page < MAX_PAGES:
                page += 1
                html = self._get(client, f"{AGENDA_URL}page/{page}/")
                items.extend(parse_list(html))
            if not items:
                raise RuntimeError("tivolivredenburg: agenda returned no events")
            # One row per detail URL (a card can't repeat, but be safe).
            items = list({i.external_id: i for i in items}.values())
            # Genre-only exclusions need no detail fetch.
            kept = [i for i in items if exclusion_reason(i, None, tree) is None]

            cache: dict[str, Detail | None] = {}

            def fetch(item: ListItem) -> Detail | None:
                if item.url not in cache:
                    try:
                        cache[item.url] = parse_detail(self._get(client, item.url))
                    except httpx.HTTPError as exc:
                        logger.warning("tivolivredenburg: detail failed %s: %s", item.url, exc)
                        cache[item.url] = None
                return cache[item.url]

            with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
                details = list(pool.map(fetch, kept))
        if kept and all(d is None for d in details):
            raise RuntimeError(f"tivolivredenburg: all {len(kept)} detail fetches failed")

        events: list[ScrapedEvent] = []
        reasons: dict[str, int] = {}
        for item in items:
            if exclusion_reason(item, None, tree):
                key = exclusion_reason(item, None, tree)
                reasons[key] = reasons.get(key, 0) + 1
        for item, detail in zip(kept, details):
            if detail is None:
                continue
            reason = exclusion_reason(item, detail, tree)
            if reason:
                key = reason.split(" (")[0]
                reasons[key] = reasons.get(key, 0) + 1
                continue
            ev = build_event(item, detail, tree)
            if ev is not None:
                events.append(ev)
        logger.info("tivolivredenburg: %d agenda items, %d kept, excluded %s",
                    len(items), len(events), reasons)
        return events


register(
    scraper=TivoliVredenburgScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="TivoliVredenburg",
        city_slug="utrecht",
        address="Vredenburgkade 11, 3511 WC Utrecht",
        site_url=BASE_URL + "/",
        instagram_url="https://www.instagram.com/tivolivredenburg",
        category_slugs=["pop", "jazz", "classical", "club", "folk", "kids"],
        list_memberships=[
            ListMembership(list_slug=cat, whitelist_category_slug=cat)
            for cat in ["pop", "jazz", "classical", "club", "folk", "kids"]
        ],
    ),
)
