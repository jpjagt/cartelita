from __future__ import annotations

import datetime as dt
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers import _cre8ion as c8
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# Podium Hoge Woerd (De Meern, Leidsche Rijn — Utrecht) — a neighbourhood
# theatre: cabaret, theatre, youth shows, dance, a few concerts. cre8ion CMS +
# Ticketmatic, server-rendered. `/agenda` shows 10 cards (`div.event.desktop`)
# per page; the "load more" XHR lives under `/mvc/`, which robots.txt
# disallows, so we page with the agenda's own date filter instead:
# `/agenda?StartDate=DD-MM-YYYY`, restarting at the last date seen (rows are
# de-duplicated per occurrence). Card: genre(s), company, title, labels
# (Try-out, series), date ("do 15 oktober", no year), time, ticket status.
# Price and hall on the programme's detail page. See
# podium_hoge_woerd_SOURCE.md (shared notes: cre8ion_SOURCE.md).
BASE_URL = "https://www.podiumhogewoerd.nl"
AGENDA_URL = BASE_URL + "/agenda"
VENUE_SLUG = "podium-hoge-woerd"
MAX_PAGES = 80

GENRE_CATEGORY = {
    "theater": "theater",
    "cabaret": "theater",
    "kleinkunst": "theater",
    "muziektheater": "theater",
    "circustheater": "theater",
    "theatertour": "theater",
    "verrassing": "theater",   # Nationaal Theaterweekend's mystery show
    "dans": "dance",
    "jeugd": "kids",
}
# "Muziek" (concerts, tribute bands) → pop, only when there is no stage genre.
MUSIC_GENRE = "muziek"
# Rentals (an amateur orchestra's new-year concert), talks and workshops are
# not the venue's programme, whatever else they're tagged.
EXCLUDED_GENRES = {"verhuur", "talks", "workshop"}
NO_LANGUAGE_LABEL = "No Dutch? No Problem!"

_SOLD_OUT = ("uitverkocht",)
_SKIP_STATUS = ("geannuleerd", "verplaatst")


def _text(el: Tag | None) -> str:
    return c8.clean(el.get_text(" ")) if el else ""


def categorize(genres: list[str]) -> list[str] | None:
    low = [g.lower() for g in genres]
    if any(g in EXCLUDED_GENRES for g in low):
        return None
    cats = list(dict.fromkeys(GENRE_CATEGORY[g] for g in low if g in GENRE_CATEGORY))
    if not cats and MUSIC_GENRE in low:
        cats = ["pop"]
    return cats or None


def _cards(html: str) -> list[Tag]:
    return BeautifulSoup(html, "html.parser").select("div.event.desktop")


def _fields(card: Tag) -> tuple[str | None, list[str], str, str]:
    """(detail URL, genres, company, title) of one card. The info link holds
    three bare spans: genre list ("Dans, No Dutch? No Problem!"), the company
    (`.titel`) and the show title."""
    a = card.select_one(".info-wrapper a[href]")
    if not a:
        return None, [], "", ""
    spans = [_text(s) for s in a.find_all("span", recursive=False)]
    genres = [g.strip() for g in (spans[0] if spans else "").split(",") if g.strip()]
    company = _text(a.select_one(".titel"))
    title = spans[2] if len(spans) > 2 else company
    return urljoin(BASE_URL, a["href"]), genres, company, title


def _status(card: Tag) -> str:
    return _text(card.select_one(".ticket-wrapper")).lower()


def _labels(card: Tag) -> list[str]:
    return [_text(t) for t in card.select(".labels .tag")]


def _skipped(card: Tag) -> bool:
    return any(s in _status(card) for s in _SKIP_STATUS) or any(
        lab.lower() in _SKIP_STATUS for lab in _labels(card)
    )


def last_date(html: str, today: dt.date) -> dt.date | None:
    dates = [c8.parse_date(_text(c.select_one(".date")), today) for c in _cards(html)]
    dates = [d for d in dates if d]
    return max(dates) if dates else None


def programme_urls(pages: list[str]) -> list[str]:
    out = []
    for html in pages:
        for card in _cards(html):
            url, genres, _, _ = _fields(card)
            if url and categorize(genres) and not _skipped(card):
                out.append(url)
    return list(dict.fromkeys(out))


def parse_agenda(
    pages: list[str], details: dict[str, str] | None = None, today: dt.date | None = None
) -> list[ScrapedEvent]:
    """Agenda pages (+ detail HTML by URL) → one event per kept performance."""
    details = details or {}
    today = today or dt.date.today()
    rows = {url: c8.parse_ticket_rows(h, today) for url, h in details.items()}
    events: dict[str, ScrapedEvent] = {}
    for html in pages:
        for card in _cards(html):
            url, genres, company, title = _fields(card)
            start_date = c8.parse_date(_text(card.select_one(".date")), today)
            if not url or not title or not start_date:
                continue
            cats = categorize(genres)
            if not cats or _skipped(card):
                continue
            start_time = c8.parse_time(_text(card.select_one(".time")))
            row = c8.match_row(rows.get(url, []), start_date, start_time)
            if row and row.has_label(*c8.SKIP_ROW_LABELS):
                continue
            if any(s in _status(card) for s in _SOLD_OUT):
                price = "sold-out"
            else:
                price = row.price if row else None
            slug = url.rstrip("/").rsplit("/", 1)[-1]
            hhmm = start_time.strftime("%H%M") if start_time else "0000"
            external_id = f"{slug}@{start_date.isoformat()}T{hhmm}"
            img = card.select_one("img[src]")
            no_language = any(g.lower() == NO_LANGUAGE_LABEL.lower() for g in genres)
            events.setdefault(external_id, ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=url,
                category_slugs=cats,
                price=price,
                description=company if company and company != title else None,
                image_url=urljoin(BASE_URL, img["src"]) if img else None,
                external_id=external_id,
                language=NO_LANGUAGE_LABEL if no_language else None,
                annotations=list(dict.fromkeys(
                    [g for g in genres if g.lower() != NO_LANGUAGE_LABEL.lower()]
                    + _labels(card) + c8.row_annotations(row)
                )),
            ))
    return list(events.values())


def fetch_pages(http, today: dt.date) -> list[str]:
    """Walk the agenda by its StartDate filter until a short page."""
    pages: list[str] = []
    start = today
    for _ in range(MAX_PAGES):
        r = http.get(AGENDA_URL, params={"StartDate": start.strftime("%d-%m-%Y")})
        r.raise_for_status()
        cards = _cards(r.text)
        if not cards:
            break
        pages.append(r.text)
        if len(cards) < 10:
            break
        last = last_date(r.text, today)
        if not last:
            break
        # Restart at the last date (its rows may continue on the next page);
        # if the whole page was one day, step past it.
        start = last if last > start else start + dt.timedelta(days=1)
    return pages


class PodiumHogeWoerdScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        today = dt.date.today()
        with c8.client() as http:
            pages = fetch_pages(http, today)
            details = c8.fetch_all(http, programme_urls(pages))
        return parse_agenda(pages, details, today)


register(
    scraper=PodiumHogeWoerdScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Podium Hoge Woerd",
        city_slug="utrecht",
        address="Hoge Woerdplein 1, 3454 PB Utrecht (De Meern)",
        site_url=BASE_URL + "/",
        instagram_url="https://www.instagram.com/podiumhogewoerd/",
        category_slugs=["theater", "dance", "kids", "pop"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
            ListMembership(list_slug="pop", whitelist_category_slug="pop"),
        ],
    ),
)
