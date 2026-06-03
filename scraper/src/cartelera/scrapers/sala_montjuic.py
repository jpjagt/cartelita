from __future__ import annotations
import datetime as dt
import html as html_module
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Sala Montjuïc is Barcelona's summer open-air cinema at the Montjuïc castle moat
# (roughly late June → early August). Its programme is a single server-rendered
# Elementor "dynamic posts" grid: one `<article class="movie">` per screening,
# carrying title, detail link, date and image — a single request is the whole
# season. The listing has NO time and NO price; the evening schedule
# ("22:00 – PEL·LÍCULA") lives on each film's detail page, which we fetch per
# screening for the film start time. See sala_montjuic_SOURCE.md.
#
# SEASONAL: outside summer the programme may be empty or unpublished — the parser
# tolerates zero cards and returns an empty list without error.
AGENDA_URL = "https://www.salamontjuic.org/programacio/"
BASE_URL = "https://www.salamontjuic.org"
VENUE_SLUG = "sala-montjuic"

# The site 403s requests without a browser UA (httpx's default UA trips it).
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Date meta on a card, e.g. "Divendres 10/07" — Catalan weekday + DD/MM, no year.
_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})")
# Sold-out flag carried as its own meta.
_SOLD_OUT_RE = re.compile(r"sold\s*out", re.I)
# The film start time on the detail page: "22:00 – PEL·LÍCULA" (vs the
# "20:45 – CONCERT" live-music opener). The separator is an en-dash on the live
# site; we read it from BeautifulSoup-extracted text, so accept any dash/space run.
_FILM_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*[\-‐-―]\s*PEL", re.I)


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").strip()


def _parse_date(day: int, month: int, today: dt.date | None = None) -> dt.date | None:
    """DD/MM with the year inferred as the current year, rolling to next year if
    the date is >90 days in the past (year-end safety) — same as Casa Figari."""
    today = today or dt.date.today()
    try:
        d = dt.date(today.year, month, day)
    except ValueError:
        return None
    if (today - d).days > 90:
        try:
            d = dt.date(today.year + 1, month, day)
        except ValueError:
            return None
    return d


def parse_film_time(html: str) -> dt.time | None:
    """The film's start time from a Sala Montjuïc detail page.

    The schedule renders as free-text widgets; the film line is
    "HH:MM – PEL·LÍCULA" (distinct from the "HH:MM – CONCERT" opener). Read it
    from the page rather than hardcoding — open-air screenings start after sunset
    and the time can shift across the season."""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    m = _FILM_TIME_RE.search(text)
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    return dt.time(hh, mm) if 0 <= hh < 24 and 0 <= mm < 60 else None


def _card_metas(card: Tag) -> list[str]:
    return [
        t
        for m in card.select(".dce-post-custommeta")
        if (t := _clean(m.get_text(" ", strip=True)))
    ]


def parse_agenda(
    html: str,
    today: dt.date | None = None,
    times: dict[str, dt.time] | None = None,
) -> list[ScrapedEvent]:
    """Parse the Sala Montjuïc programme page into ScrapedEvents.

    One ScrapedEvent per `article.movie`: title + detail URL from `h3 a`, date
    from the `Weekday DD/MM` meta (year inferred), image from the card, the
    live-music act as a free-form annotation, and `"sold-out"` price when the card
    carries a SOLD OUT meta. Every screening is category `film`.

    `times` maps `source_url` → film start time (read from the detail pages by the
    Scraper); offline callers may omit it (start_time then None). The programme is
    seasonal: an empty page yields an empty list."""
    times = times or {}
    soup = BeautifulSoup(html, "html.parser")

    events: list[ScrapedEvent] = []
    for card in soup.select("article.movie"):
        link = card.select_one("h3.dce-post-title a[href]")
        href = card.get("data-post-link") or (link.get("href") if link else None)
        title = _clean(link.get_text(strip=True)) if link else None
        if not title or not href:
            continue
        source_url = href.split("?")[0]

        metas = _card_metas(card)
        start_date: dt.date | None = None
        price: str | None = None
        annotations: list[str] = []
        for meta in metas:
            if _SOLD_OUT_RE.search(meta):
                price = "sold-out"
                continue
            dm = _DATE_RE.search(meta)
            if dm and start_date is None:
                start_date = _parse_date(int(dm.group(1)), int(dm.group(2)), today)
                continue
            # Anything else is the live-music act that opens the night.
            annotations.append(meta)

        if start_date is None:
            continue  # no reliable date; skip rather than guess

        img = card.select_one(".dce-post-image img[src]")
        image_url = img.get("src") if img else None

        slug = source_url.rstrip("/").rsplit("/", 1)[-1]
        external_id = f"{slug}@{start_date.isoformat()}" if slug else None

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=times.get(source_url),
                source_url=source_url,
                category_slugs=["film"],
                price=price,
                image_url=image_url,
                external_id=external_id,
                annotations=annotations,
            )
        )

    return events


class SalaMontjuicScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with httpx.Client(follow_redirects=True, timeout=30, headers=_HEADERS) as client:
            html = client.get(AGENDA_URL).text
            # First pass: get the cards (and their detail URLs) without times.
            stub_events = parse_agenda(html)
            # Fetch each detail page once for the film start time.
            times: dict[str, dt.time] = {}
            for ev in stub_events:
                try:
                    detail = client.get(ev.source_url).text
                except httpx.HTTPError:
                    continue
                t = parse_film_time(detail)
                if t is not None:
                    times[ev.source_url] = t
            return parse_agenda(html, times=times)


register(
    scraper=SalaMontjuicScraper(),
    venue=VenueDefinition(
        slug="sala-montjuic",
        name="Sala Montjuïc",
        city_slug="barcelona",
        address="Castell de Montjuïc, Carretera de Montjuïc, 66, 08038 Barcelona",
        site_url="https://www.salamontjuic.org",
        category_slugs=["film"],
        list_memberships=[
            ListMembership(list_slug="film"),
        ],
    ),
)
