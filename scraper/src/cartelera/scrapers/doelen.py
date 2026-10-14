"""De Doelen + Theater Zuidplein (Rotterdam) — one source, two venues.

Both sites run CultureSuite's "Peppered" CMS with the same agenda template
(`li.eventCard`, paginated `?p54_page=N`), each behind a CultureSuite queue
gate ("csq"): at busy moments a plain GET 307s to `/csq/` until a JavaScript
challenge sets a `csq_token` cookie. We try plain HTTP first; on a gate we do
ONE headless pass per site with the shared browser helper
(`cartelera.scrapers.browser`), then fetch every page over plain HTTP with that
cookie + the same User-Agent. See doelen_SOURCE.md.

Per card: production title/subtitle/detail link/genres; occurrences are the
card's `li.subshow` rows when present (multi-date productions), else the card
itself. Per occurrence: start from `data-event-start` (fallback: the "wo 14 okt
[26]" + time text, year inferred from the weekday), hall (`.venue`), and the
price popover table (`tr > .pricetype` + `.price`).

Category = the venue's OWN genre labels (never title keywords); events whose
labels map to none of our categories, or that carry an exclusion label
(Doelen "talk"; Zuidplein "Overig", "Gastprogramma"), are left out — see
the SOURCE.md for the reasoning per label.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register_source
from cartelera.scrapers.browser import BROWSER_HELPER_UA, browser_page
from cartelera.types import ListMembership, ScrapedEvent, SourceDefinition, VenueDefinition

SOURCE_SLUG = "doelen"
DOELEN = "de-doelen"
ZUIDPLEIN = "theater-zuidplein"

_MAX_PAGES = 60
# A short subtitle is the performer ("Fred van Leer", "Rotterdams Philharmonisch
# Orkest") and belongs in the title; a long one is a blurb (-> description).
_SUBTITLE_MAX = 40


@dataclass(frozen=True)
class Site:
    venue_slug: str
    base_url: str
    agenda_path: str
    # genre label (lowercased) -> category slug
    genre_map: dict[str, str]
    # labels whose presence excludes the event (non-programme items)
    exclude_genres: frozenset[str]
    # a label that, when present, makes the event ONLY this category
    exclusive: dict[str, str]


SITES = {
    DOELEN: Site(
        venue_slug=DOELEN,
        base_url="https://www.dedoelen.nl",
        agenda_path="/nl/agenda",
        genre_map={"klassiek": "classical", "jazz": "jazz", "pop": "pop", "global": "folk"},
        exclude_genres=frozenset({"talk"}),
        exclusive={},
    ),
    ZUIDPLEIN: Site(
        venue_slug=ZUIDPLEIN,
        base_url="https://www.theaterzuidplein.nl",
        agenda_path="/agenda",
        genre_map={
            "toneel": "theater", "muziektheater": "theater", "comedy / cabaret": "theater",
            "stand up": "theater", "theater": "theater", "bewegingstheater": "theater",
            "mime (woordloos)": "theater", "poppentheater": "theater", "musical": "theater",
            "opera": "theater", "storytelling": "theater", "verteltheater": "theater",
            "spoken word": "theater", "crossover": "theater",
            "dans": "dance",
            "popmuziek": "pop", "muziek": "pop", "hiphop": "pop",
            "wereldmuziek": "folk",
        },
        exclude_genres=frozenset({"overig", "gastprogramma"}),
        exclusive={"jeugd & familie": "kids"},
    ),
}

_MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "maa": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}
_WEEKDAYS = {"ma": 0, "di": 1, "wo": 2, "do": 3, "vr": 4, "za": 5, "zo": 6}
_DATE_TEXT = re.compile(r"(ma|di|wo|do|vr|za|zo)\w*\s+(\d{1,2})\s+([a-z]{3})\w*\.?(?:\s+(\d{2,4}))?", re.I)
_TIME_TEXT = re.compile(r"\b(\d{1,2})[:.](\d{2})\b")
_EUR = re.compile(r"€\s*(\d+(?:[.,]\d{1,2})?)")
# Price tiers that are not the regular public price.
_SKIP_PRICETYPE = re.compile(
    r"t/m|tot \d|jong|student|cjp|kind|65\+|korting|early|supporter|pay what|dinner|diner",
    re.I,
)
# Status prefixes the editors put in titles: "uitverkocht | Outlander in Concert".
_TITLE_STATUS = re.compile(r"^\s*(geannuleerd|afgelast|uitverkocht|verplaatst|extra voorstelling)\s*\|\s*", re.I)
# Marketing labels in the genre list that say nothing about the content.
_NOISE_LABELS = re.compile(r"tarief|seizoen|jubileum|^gratis$", re.I)
_CANCELLED_HALLS = re.compile(r"geannuleerd|vervallen|afgelast", re.I)


def _text(el: Tag | None) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def _amount(raw: str) -> float:
    return float(raw.replace(",", "."))


def _fmt(v: float) -> str:
    return str(int(v)) if v == int(v) else f"{v:.2f}".replace(".", ",")


def format_price(amounts: list[float]) -> str | None:
    if not amounts:
        return None
    lo, hi = min(amounts), max(amounts)
    if hi == 0:
        return "free"
    if lo > 0 and hi >= 2 * lo:
        return f"{_fmt(lo)}–{_fmt(hi)}€"
    return f"{_fmt(hi)}€"


def _price(node: Tag) -> str | None:
    """Price for one occurrence node (a subshow row or a single-date card)."""
    classes = " ".join(" ".join(x.get("class", [])) for x in node.select('[class*="status-"]'))
    if "status-uitverkocht" in classes:
        return "sold-out"
    if "status-vrij_entree" in classes:
        return "free"
    rows = [tr for tr in node.select(".item-prices tr") if "rank" not in tr.get("class", [])]
    priced = []
    for tr in rows:
        cell = tr.select_one("td.price")
        if cell is None:
            continue
        priced.append((_text(tr.select_one(".pricetype")), _text(cell), "is-soldout" in tr.get("class", [])))
    if priced and all(sold or "uitverkocht" in p.lower() for _, p, sold in priced):
        return "sold-out"
    regular = [_amount(m) for t, p, _ in priced if not _SKIP_PRICETYPE.search(t) for m in _EUR.findall(p)]
    if regular:
        return format_price(regular)
    if priced and all(re.search(r"pay what", t, re.I) for t, _, _ in priced):
        return "pay what you can"
    return None


def _infer_date(weekday: int, day: int, month: int, today: dt.date) -> dt.date | None:
    """A yearless "wo 14 okt": the year (around today) whose weekday matches."""
    for year in (today.year, today.year + 1, today.year - 1, today.year + 2):
        try:
            d = dt.date(year, month, day)
        except ValueError:
            continue
        if d.weekday() == weekday:
            return d
    return None


def _parse_date_text(text: str, today: dt.date) -> dt.date | None:
    m = _DATE_TEXT.search(text)
    if not m:
        return None
    wd, day, mon, year = m.group(1).lower()[:2], int(m.group(2)), m.group(3).lower()[:3], m.group(4)
    month = _MONTHS.get(mon)
    if month is None:
        return None
    if year:
        y = int(year)
        return dt.date(y + 2000 if y < 100 else y, month, day)
    return _infer_date(_WEEKDAYS[wd], day, month, today)


def _start(node: Tag, today: dt.date) -> tuple[dt.date, dt.time | None] | None:
    attr = node.select_one("[data-event-start]")
    if attr and attr.get("data-event-start"):
        try:
            when = dt.datetime.strptime(attr["data-event-start"], "%Y-%m-%d %H:%M:%S")
            return when.date(), when.time()
        except ValueError:
            pass
    date_el = node.select_one(".date .start") or node.select_one(".top-date .start")
    d = _parse_date_text(_text(date_el), today)
    if d is None:
        return None
    # Doelen subshows list "deuren open 19:15 / start 20:15 / pauze": take the
    # emphasised "start"; elsewhere the `.time` span.
    time_el = node.select_one("dl.intermission strong + *") or node.select_one("dl.intermission dd strong")
    if time_el is None:
        time_el = node.select_one(".time .start") or node.select_one(".top-date .time") or node.select_one(".time")
    m = _TIME_TEXT.search(_text(time_el))
    t = dt.time(int(m.group(1)), int(m.group(2))) if m and int(m.group(1)) < 24 else None
    return d, t


def categories_for(site: Site, genres: list[str]) -> list[str]:
    """Category slugs from the venue's own genre labels; [] = leave out."""
    low = [g.lower() for g in genres]
    if any(g in site.exclude_genres for g in low):
        return []
    for label, cat in site.exclusive.items():
        if label in low:
            return [cat]
    cats: list[str] = []
    for g in low:
        cat = site.genre_map.get(g)
        if cat and cat not in cats:
            cats.append(cat)
    return cats


def parse_agenda(html: str, site: Site, today: dt.date | None = None) -> list[ScrapedEvent]:
    """One agenda page -> one ScrapedEvent per (kept) occurrence. Pure."""
    today = today or dt.date.today()
    soup = BeautifulSoup(html, "html.parser")
    events: list[ScrapedEvent] = []
    for card in soup.select("li.eventCard"):
        title = _text(card.select_one(".title"))
        status = _TITLE_STATUS.match(title)
        status_word = status.group(1).lower() if status else None
        if status:
            title = title[status.end():].strip()
        if not title or status_word in ("geannuleerd", "afgelast"):
            continue
        genres = [_text(a) for a in card.select(".genres__link")]
        cats = categories_for(site, genres)
        if not cats:
            continue
        link = card.select_one("a.desc[href]") or card.select_one("a[href]")
        source_url = urljoin(site.base_url, link["href"]) if link else site.base_url + site.agenda_path
        subtitle = _text(card.select_one(".subtitle")) or None
        tagline = _text(card.select_one(".tagline")) or None
        img = card.select_one(".thumb img[src]")
        image_url = img["src"] if img else None
        entry_id = card.get("data-entry-id") or re.sub(r"\W+", "-", title.lower())
        mapped = set(site.genre_map) | set(site.exclusive)
        language = None
        low = [g.lower() for g in genres]
        if "nederlandstalig" in low:
            language = "NL"
        elif "mime (woordloos)" in low:
            language = "non-verbal"

        subs = card.select("li.subshow")
        if subs:
            nodes = subs
        else:
            single = BeautifulSoup(str(card), "html.parser").select_one("li.eventCard")
            for x in single.select(".subshows"):
                x.decompose()
            nodes = [single]
        for node in nodes:
            if node.select_one(".status-geannuleerd") or node.select_one(".status-test"):
                continue
            start = _start(node, today)
            if start is None:
                continue
            start_date, start_time = start
            if start_date < today:
                continue
            hall = _text(node.select_one(".venue")) or None
            if hall and _CANCELLED_HALLS.search(hall):
                continue
            price = "sold-out" if status_word == "uitverkocht" else _price(node)
            annotations = [
                g for g in genres if g.lower() not in mapped and not _NOISE_LABELS.search(g)
            ]
            if hall:
                annotations.append(hall)
            if status_word == "verplaatst":
                annotations.append("verplaatst")
            hhmm = start_time.strftime("%H%M") if start_time else "0000"
            events.append(ScrapedEvent(
                title=f"{title} — {subtitle}" if subtitle and len(subtitle) <= _SUBTITLE_MAX else title,
                start_date=start_date,
                start_time=start_time,
                source_url=source_url,
                category_slugs=list(cats),
                price=price,
                description=" — ".join(x for x in (subtitle, tagline) if x) or None,
                image_url=image_url,
                external_id=f"{entry_id}@{start_date.isoformat()}T{hhmm}",
                language=language,
                annotations=annotations,
                venue_slug=site.venue_slug,
            ))
    return events


def next_page_url(html: str, site: Site) -> str | None:
    a = BeautifulSoup(html, "html.parser").select_one("a.next[href]")
    return urljoin(site.base_url, a["href"]).split("#")[0] if a else None


def _gated(resp: httpx.Response) -> bool:
    return resp.is_redirect and "/csq" in resp.headers.get("location", "") or (
        len(resp.content) < 200 and b"queue" in resp.content
    )


class _Fetcher:
    """Plain HTTP; on the queue gate, one headless pass for the cookie."""

    def __init__(self, site: Site):
        self.site = site
        self.headers = {"User-Agent": BROWSER_HELPER_UA}
        self.browsed = False

    def get(self, url: str) -> str:
        with httpx.Client(headers=self.headers, timeout=60, follow_redirects=False) as c:
            resp = c.get(url)
        if _gated(resp):
            if self.browsed:
                raise RuntimeError(f"{url}: still queue-gated after a browser pass")
            page = browser_page(
                self.site.base_url + self.site.agenda_path, wait_for="li.eventCard", timeout=240
            )
            self.browsed = True
            self.headers = {"User-Agent": page.user_agent, "Cookie": page.cookie_header}
            return self.get(url)
        if resp.is_redirect:
            return self.get(urljoin(url, resp.headers["location"]))
        resp.raise_for_status()
        return resp.text


def scrape_site(site: Site) -> list[ScrapedEvent]:
    fetcher = _Fetcher(site)
    url: str | None = site.base_url + site.agenda_path
    events: list[ScrapedEvent] = []
    seen_pages: set[str] = set()
    for _ in range(_MAX_PAGES):
        if url is None or url in seen_pages:
            break
        seen_pages.add(url)
        html = fetcher.get(url)
        events.extend(parse_agenda(html, site))
        url = next_page_url(html, site)
    unique: dict[str, ScrapedEvent] = {}
    for ev in events:
        unique.setdefault(ev.external_id, ev)
    return list(unique.values())


class DoelenScraper:
    def scrape(self) -> list[ScrapedEvent]:
        return scrape_site(SITES[DOELEN]) + scrape_site(SITES[ZUIDPLEIN])


def _memberships(cats: list[str]) -> list[ListMembership]:
    return [ListMembership(list_slug=c, whitelist_category_slug=c) for c in cats]


_DOELEN_CATS = ["classical", "jazz", "pop", "folk"]
_ZUIDPLEIN_CATS = ["theater", "dance", "kids", "pop", "folk"]

register_source(
    scraper=DoelenScraper(),
    source=SourceDefinition(
        slug=SOURCE_SLUG,
        name="De Doelen / Theater Zuidplein",
        venues=[
            VenueDefinition(
                slug=DOELEN,
                name="De Doelen",
                city_slug="rotterdam",
                address="Schouwburgplein 50, 3012 CL Rotterdam",
                site_url="https://www.dedoelen.nl",
                instagram_url="https://www.instagram.com/dedoelen",
                category_slugs=_DOELEN_CATS,
                list_memberships=_memberships(_DOELEN_CATS),
            ),
            VenueDefinition(
                slug=ZUIDPLEIN,
                name="Theater Zuidplein",
                city_slug="rotterdam",
                address="Zuidplein 60-64, 3083 CW Rotterdam",
                site_url="https://www.theaterzuidplein.nl",
                instagram_url="https://www.instagram.com/theaterzuidplein",
                category_slugs=_ZUIDPLEIN_CATS,
                list_memberships=_memberships(_ZUIDPLEIN_CATS),
            ),
        ],
    ),
)
