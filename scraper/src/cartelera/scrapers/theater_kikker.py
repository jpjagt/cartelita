from __future__ import annotations

import datetime as dt
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers import _cre8ion as c8
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# Theater Kikker (Ganzenmarkt, Utrecht) — a small two-hall theatre for young
# makers, youth theatre and dance. cre8ion CMS + Ticketmatic, server-rendered.
# `/agenda` renders the WHOLE season in one page: one `div.event.desktop` card
# per performance (plus a `.mobile` twin we skip) with title, company, genre,
# date ("wo 14 oktober", no year), time and ticket status. Price and hall live
# on the programme's detail page (`.ticket-row.desktop` per date). See
# theater_kikker_SOURCE.md (shared notes: cre8ion_SOURCE.md).
BASE_URL = "https://www.theaterkikker.nl"
AGENDA_URL = BASE_URL + "/agenda"
VENUE_SLUG = "theater-kikker"

# The `.genre` labels → categories. "Jeugd" is Kikker's youth programme
# (all "3+"…"8+" family shows), so it maps to kids alone.
GENRE_CATEGORY = {
    "theater": "theater",
    "muziektheater": "theater",
    "performance": "theater",
    "storytelling": "theater",
    "dans": "dance",
    "jeugd": "kids",
}
# Rentals are not Kikker's programme.
EXCLUDED_GENRES = {"verhuur"}
NO_LANGUAGE_LABEL = "Language no problem"
# Kikker's own halls; "Kikker op Locatie" / "Kikker X …" rows play elsewhere
# (Theater Utrecht's Boorstraat 107, SSBU, community venues) — those venues own
# their events, so rows whose detail hall isn't one of these are left out.
HALLS = {"grote zaal", "kleine zaal"}

_SOLD_OUT = ("uitverkocht",)
_SKIP_STATUS = ("geannuleerd", "verplaatst")


def _text(el: Tag | None) -> str:
    return c8.clean(el.get_text(" ")) if el else ""


def _genres(card: Tag) -> list[str]:
    return [g.strip() for g in _text(card.select_one(".genre")).split(",") if g.strip()]


def categorize(genres: list[str]) -> list[str] | None:
    low = [g.lower() for g in genres]
    if any(g in EXCLUDED_GENRES for g in low):
        return None
    cats = list(dict.fromkeys(GENRE_CATEGORY[g] for g in low if g in GENRE_CATEGORY))
    return cats or None


def _cards(html: str) -> list[Tag]:
    return BeautifulSoup(html, "html.parser").select("div.event.desktop")


def _url(card: Tag) -> str | None:
    a = card.select_one("a.event-link[href]") or card.select_one("a[href^='/agenda/']")
    return urljoin(BASE_URL, a["href"]) if a else None


def _status(card: Tag) -> str:
    return _text(card.select_one(".ticket-wrapper")).lower()


def programme_urls(html: str) -> list[str]:
    """Detail pages worth fetching: programmes with a kept, non-skipped card."""
    out = []
    for card in _cards(html):
        url = _url(card)
        if url and categorize(_genres(card)) and not any(s in _status(card) for s in _SKIP_STATUS):
            out.append(url)
    return list(dict.fromkeys(out))


def parse_agenda(
    html: str, details: dict[str, str] | None = None, today: dt.date | None = None
) -> list[ScrapedEvent]:
    """The agenda page (+ detail HTML by URL) → one event per kept performance."""
    details = details or {}
    today = today or dt.date.today()
    rows = {url: c8.parse_ticket_rows(h, today) for url, h in details.items()}
    events: dict[str, ScrapedEvent] = {}
    for card in _cards(html):
        url = _url(card)
        title = _text(card.select_one(".titel"))
        start_date = c8.parse_date(_text(card.select_one(".date")), today)
        if not url or not title or not start_date:
            continue
        genres = _genres(card)
        cats = categorize(genres)
        status = _status(card)
        if not cats or any(s in status for s in _SKIP_STATUS):
            continue
        start_time = c8.parse_time(_text(card.select_one(".time")))
        row = c8.match_row(rows.get(url, []), start_date, start_time)
        if row and (row.location or "").lower() not in HALLS:
            continue
        if row and row.has_label(*c8.SKIP_ROW_LABELS):
            continue
        if any(s in status for s in _SOLD_OUT):
            price = "sold-out"
        else:
            price = row.price if row else None
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        hhmm = start_time.strftime("%H%M") if start_time else "0000"
        external_id = f"{slug}@{start_date.isoformat()}T{hhmm}"
        company = _text(card.select_one(".gezelschap"))
        oneliner = _text(card.select_one(".oneliner"))
        themes = [_text(i) for i in card.select(".kikker-kompas .item")]
        img = card.select_one("img[src]")
        events.setdefault(external_id, ScrapedEvent(
            title=title,
            start_date=start_date,
            start_time=start_time,
            source_url=url,
            category_slugs=cats,
            price=price,
            description=" — ".join(x for x in (company, oneliner) if x) or None,
            image_url=urljoin(BASE_URL, img["src"]) if img else None,
            external_id=external_id,
            language=NO_LANGUAGE_LABEL if any(g.lower() == NO_LANGUAGE_LABEL.lower() for g in genres) else None,
            annotations=list(dict.fromkeys(
                [g for g in genres if g.lower() != NO_LANGUAGE_LABEL.lower()]
                + themes + c8.row_annotations(row)
            )),
        ))
    return list(events.values())


class TheaterKikkerScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with c8.client() as http:
            r = http.get(AGENDA_URL)
            r.raise_for_status()
            details = c8.fetch_all(http, programme_urls(r.text))
        return parse_agenda(r.text, details)


register(
    scraper=TheaterKikkerScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Theater Kikker",
        city_slug="utrecht",
        address="Ganzenmarkt 14, 3512 GD Utrecht",
        site_url=BASE_URL + "/",
        instagram_url="https://www.instagram.com/theaterkikker/",
        category_slugs=["theater", "dance", "kids"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
