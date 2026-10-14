from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers import _cre8ion as c8
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# Stadsschouwburg Utrecht (SSBU) — Utrecht's municipal theatre (Grote Zaal,
# Blauwe Zaal, Hekman Zaal + foyers). cre8ion CMS, Ticketmatic tickets, fully
# server-rendered. The agenda is ONE row per performance, 30 per page
# (`/agenda?page=N`, ~600 performances / ~20 pages); date, time, hall, genre
# and ticket status are on the list, the price only on the programme's detail
# page (one per programme, its ticket blocks list every date with its price).
# Kids and "language no problem" are the site's own filters (`?tag=...`), so
# those sets come from filtered list pages. See
# stadsschouwburg_utrecht_SOURCE.md (shared notes: cre8ion_SOURCE.md).
BASE_URL = "https://stadsschouwburg-utrecht.nl"
AGENDA_URL = BASE_URL + "/agenda"
VENUE_SLUG = "stadsschouwburg-utrecht"

# The site's own age filters for 0–4 and 4–12 year olds (a union query).
KIDS_QUERY = "tag=spruitjes-0-tot-4-jaar&tag=kinderen-4-tot-12-jaar"
NO_LANGUAGE_QUERY = "tag=language-no-problem"
NO_LANGUAGE_LABEL = "Language no problem"
MAX_PAGES = 60

# Genre labels (`span.tag` on a list row) → our categories.
THEATER_GENRES = {
    "toneel", "cabaret", "muziektheater", "musical", "show", "mime",
    "spoken word", "circus",
}
GENRE_CATEGORY = {g: "theater" for g in THEATER_GENRES} | {
    "dans": "dance",
    "opera": "classical",
}
# "Muziek" (concerts: Popronde, Le Guess Who?, singer-songwriters) → pop, but
# only when the row has no stage genre (a "Muziek, Dans" baby show is dance).
MUSIC_GENRE = "muziek"
# Lecture / amateur formats: never programme, whatever else they're tagged.
EXCLUDED_GENRES = {"theatercollege", "amateuruitvoering"}
# Talks/dinners: not a category on their own (a row with only these — e.g. a
# "Verdieping" workshop or a "Foodprogramma" tasting — is left out), but they
# don't disqualify a show ("Lachen met Volle Mond" = Foodprogramma + Cabaret).
SIDE_GENRES = {"verdieping", "foodprogramma"}
# Rows SSBU lists in rooms that aren't SSBU's: KABUL à GoGo is the club in the
# building with its own programme and owning source (`kabul-a-gogo`, batch 6);
# Fort aan de Klop is an off-site summer location.
EXCLUDED_LOCATIONS = {"kabul à gogo", "fort aan de klop"}

_FREE_STATUS = ("vrije inloop", "gratis", "vrij te bezoeken")
_SOLD_OUT_STATUS = ("uitverkocht",)
_CANCELLED_STATUS = ("geannuleerd",)
_DATETIME = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})\s+(\d{1,2}):(\d{2})")
_PROGRAMME_ID = re.compile(r"\d+")


@dataclass
class Row:
    """One performance row of the agenda list."""
    url: str
    programme_id: str
    title: str
    company: str | None
    oneliner: str | None
    start_date: dt.date
    start_time: dt.time | None
    genres: list[str]
    labels: list[str]          # festival/series links (`a.tag`)
    flags: list[str]           # "reprise", "première", ...
    location: str | None
    status: str
    cancelled: bool
    image_url: str | None


def _text(el: Tag | None) -> str:
    return c8.clean(el.get_text(" ")) if el else ""


def parse_rows(html: str) -> list[Row]:
    """Every performance row on one agenda page (pure)."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[Row] = []
    for li in soup.select("ul.events-list > li.paging-container"):
        a = li.select_one("h3.title a[href]")
        when = li.select_one("time[datetime]")
        if not a or not when:
            continue
        m = _DATETIME.search(when["datetime"])
        if not m:
            continue
        d, mo, y, hh, mm = (int(x) for x in m.groups())
        try:
            start_date = dt.date(y, mo, d)
        except ValueError:
            continue
        start_time = dt.time(hh, mm) if (hh, mm) != (0, 0) else None
        subtitles = li.select("p.subtitle")
        company = next((_text(p) for p in subtitles if "oneliner" not in p["class"]), None)
        oneliner = next((_text(p) for p in subtitles if "oneliner" in p["class"]), None)
        tags = li.select(".tag-wrapper .tag")
        genres = [_text(t) for t in tags if t.name == "span" and "only-mobile" not in t["class"]]
        cancelled = any(_text(t).lower() == "geannuleerd" for t in tags)
        genres = [g for g in dict.fromkeys(genres) if g.lower() != "geannuleerd"]
        labels = [_text(t) for t in tags if t.name == "a"]
        button = li.select_one(".btn-wrapper .btn-ticket span") or li.select_one(".btn-ticket")
        status = _text(button).lower()
        flags = [_text(s) for s in li.select(".date-wrapper-mobile > span")]
        img = li.select_one("img[src]")
        pid = a.get("data-detail-link") or ""
        rows.append(Row(
            url=urljoin(BASE_URL, a["href"]),
            programme_id=pid if _PROGRAMME_ID.fullmatch(pid) else a["href"].rsplit("/", 1)[-1],
            title=_text(a),
            company=company or None,
            oneliner=oneliner or None,
            start_date=start_date,
            start_time=start_time,
            genres=genres,
            labels=labels,
            flags=[f for f in flags if f],
            location=_text(li.select_one(".location")) or None,
            status=status,
            cancelled=cancelled or any(s in status for s in _CANCELLED_STATUS),
            image_url=img["src"] if img else None,
        ))
    return rows


def page_count(html: str) -> int:
    """Highest page number in the pager (1 when there is no pager)."""
    soup = BeautifulSoup(html, "html.parser")
    nums = [int(n) for n in (_text(s) for s in soup.select(".page-numbers .page-number")) if n.isdigit()]
    return max(nums, default=1)


def programme_urls(pages: list[str]) -> set[str]:
    return {r.url for html in pages for r in parse_rows(html)}


def categorize(genres: list[str]) -> list[str] | None:
    """The row's genre labels → categories, or None to leave the row out."""
    low = [g.lower() for g in genres]
    if any(g in EXCLUDED_GENRES for g in low):
        return None
    cats = list(dict.fromkeys(GENRE_CATEGORY[g] for g in low if g in GENRE_CATEGORY))
    if not cats and MUSIC_GENRE in low:
        cats = ["pop"]
    return cats or None


def keep(row: Row) -> bool:
    if row.cancelled:
        return False
    if (row.location or "").lower() in EXCLUDED_LOCATIONS:
        return False
    return categorize(row.genres) is not None


@dataclass
class Detail:
    prices: dict[tuple[dt.date, dt.time | None], str | None]
    description: str | None


def _block_price(block: Tag) -> str | None:
    price_el = block.select_one(".price-text")
    if not price_el:
        return None
    text = _text(price_el).lower()
    # The bold group is the public price per seat rank ("€ 25 / € 21 / € 15");
    # the rest are reduced tiers ("t/m 18 jaar € 12") we skip.
    tiers = [a for s in price_el.find_all("strong", recursive=False) for a in c8.amounts(_text(s))]
    if not tiers:
        tiers = c8.amounts(text)[:1]
    if tiers:
        return c8.format_tiers(tiers)
    if "gratis" in text or "vrije toegang" in text or "free" in text:
        return "free"
    return None


def parse_detail(html: str, today: dt.date) -> Detail:
    """A programme detail page → price per (date, time) and the description."""
    soup = BeautifulSoup(html, "html.parser")
    prices: dict[tuple[dt.date, dt.time | None], str | None] = {}
    for block in soup.select("#ticket-blocks-container .ticket-block"):
        date = c8.parse_date(_text(block.select_one(".date-text")), today)
        if not date:
            continue
        time_el = block.select_one(".time-text")
        start = c8.parse_time(_text(time_el)) if time_el else None
        prices.setdefault((date, start), _block_price(block))
    description = None
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("description"):
            description = c8.clean(BeautifulSoup(data["description"], "html.parser").get_text(" "))
            break
    return Detail(prices=prices, description=description or None)


def _price(row: Row, detail: Detail | None) -> str | None:
    if any(s in row.status for s in _SOLD_OUT_STATUS):
        return "sold-out"
    if any(s in row.status for s in _FREE_STATUS):
        return "free"
    if not detail:
        return None
    key = (row.start_date, row.start_time)
    if key in detail.prices:
        return detail.prices[key]
    same_day = [p for (d, _), p in detail.prices.items() if d == row.start_date]
    if same_day:
        return same_day[0]
    distinct = set(detail.prices.values())
    return distinct.pop() if len(distinct) == 1 else None


def parse_agenda(
    pages: list[str],
    details: dict[str, str] | None = None,
    kids: set[str] | None = None,
    no_language: set[str] | None = None,
    today: dt.date | None = None,
) -> list[ScrapedEvent]:
    """Agenda pages (+ detail HTML by programme URL, the kids / language-no-
    problem programme URL sets) → one ScrapedEvent per kept performance."""
    details = details or {}
    kids = kids or set()
    no_language = no_language or set()
    today = today or dt.date.today()
    parsed = {url: parse_detail(html, today) for url, html in details.items()}
    events: dict[str, ScrapedEvent] = {}
    for html in pages:
        for row in parse_rows(html):
            if not keep(row):
                continue
            cats = categorize(row.genres) or []
            if row.url in kids and "kids" not in cats:
                cats = ["kids", *cats]
            detail = parsed.get(row.url)
            hhmm = row.start_time.strftime("%H%M") if row.start_time else "0000"
            external_id = f"{row.programme_id}@{row.start_date.isoformat()}T{hhmm}"
            description = " — ".join(x for x in (row.company, row.oneliner) if x) or None
            events.setdefault(external_id, ScrapedEvent(
                title=row.title,
                start_date=row.start_date,
                start_time=row.start_time,
                source_url=row.url,
                category_slugs=cats,
                price=_price(row, detail),
                description=description or (detail.description if detail else None),
                image_url=row.image_url,
                external_id=external_id,
                language=NO_LANGUAGE_LABEL if row.url in no_language else None,
                annotations=list(dict.fromkeys(row.genres + row.labels + row.flags)),
            ))
    return list(events.values())


def _paged(http, query: str) -> list[str]:
    """All pages of an agenda listing (`query` = filter params, may be "")."""
    sep = "&" if query else ""
    pages: list[str] = []
    page = 1
    total = 1
    while page <= min(total, MAX_PAGES):
        r = http.get(f"{AGENDA_URL}?{query}{sep}page={page}")
        r.raise_for_status()
        if not parse_rows(r.text):
            break
        pages.append(r.text)
        total = max(total, page_count(r.text))
        page += 1
    return pages


class StadsschouwburgUtrechtScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with c8.client() as http:
            pages = _paged(http, "")
            kids = programme_urls(_paged(http, KIDS_QUERY))
            no_language = programme_urls(_paged(http, NO_LANGUAGE_QUERY))
            # Detail pages only for programmes with a kept row whose price
            # isn't already settled by its list status.
            wanted = [
                r.url for html in pages for r in parse_rows(html)
                if keep(r) and not any(s in r.status for s in _SOLD_OUT_STATUS + _FREE_STATUS)
            ]
            details = c8.fetch_all(http, wanted)
        return parse_agenda(pages, details, kids, no_language)


register(
    scraper=StadsschouwburgUtrechtScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Stadsschouwburg Utrecht",
        city_slug="utrecht",
        address="Lucasbolwerk 24, 3512 EH Utrecht",
        site_url=BASE_URL + "/",
        instagram_url="https://www.instagram.com/ssbutrecht/",
        category_slugs=["theater", "dance", "kids", "classical", "pop"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
            ListMembership(list_slug="classical", whitelist_category_slug="classical"),
            ListMembership(list_slug="pop", whitelist_category_slug="pop"),
        ],
    ),
)
