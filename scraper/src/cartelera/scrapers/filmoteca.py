from __future__ import annotations
import datetime as dt
import html as html_module
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Filmoteca de Catalunya's weekly agenda server-renders every screening of the
# week as `.card` elements grouped into `.block-day` sections (one per day). The
# card carries everything we need — title, detail link, local showtime, image and
# the programming cycle — so a single request per week is a complete source (no
# per-film detail fetch). See filmoteca_SOURCE.md.
#
# The page also has a `.listado-agenda` sidebar listing week-level exhibitions/
# cycles; that is NOT the screenings and we ignore it.
AGENDA_URL = "https://www.filmoteca.cat/web/ca/view-agenda-setmanal"
BASE_URL = "https://www.filmoteca.cat"
VENUE_SLUG = "filmoteca"

# How many weeks (incl. the current one) to scrape, stepping `?w=` forward by 7d.
_WEEKS_AHEAD = 6

# The Google-Calendar "add to calendar" link embedded in each card's popover
# carries `dates=YYYYMMDDThhmmss` (in UTC). We use only its DATE part — the local
# showtime comes from `.hour`, so no timezone math is needed (afternoon/evening
# screenings never cross a UTC day boundary).
_GCAL_DATE = re.compile(r"dates=(\d{4})(\d{2})(\d{2})")
_HOUR = re.compile(r"(\d{1,2}):(\d{2})")


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").strip()


def _absolutize(url: str) -> str:
    # The fixture mixes http:// and protocol-relative/relative image hosts; pin
    # everything to https on the canonical host.
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = BASE_URL + url
    return url.replace("http://www.filmoteca.cat", "https://www.filmoteca.cat")


def _card_title_and_url(card: Tag) -> tuple[str | None, str | None]:
    link = card.select_one(".content-card .titl a[href]")
    if not link:
        return None, None
    title = _clean(link.get_text(strip=True))
    href = link.get("href", "").split("?")[0].rstrip("/")
    return (title or None), (_absolutize(href) if href else None)


def _card_date(card: Tag) -> dt.date | None:
    """Date from the Google-Calendar link's `dates=YYYYMMDD...` (UTC date part)."""
    pop = card.select_one("[data-content]")
    raw = pop.get("data-content", "") if pop else ""
    m = _GCAL_DATE.search(raw)
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _card_time(card: Tag) -> dt.time | None:
    el = card.select_one(".content-card-header .hour")
    if not el:
        return None
    m = _HOUR.search(el.get_text(strip=True))
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    return dt.time(hh, mm) if 0 <= hh < 24 and 0 <= mm < 60 else None


def _card_description(content: Tag) -> str | None:
    """Alt-language title plus the director/year line, joined.

    Within `.content-card` the first direct `.description.mini_text-1` is the
    alternate-language title; a `.more-info > .description.mini_text-1` holds the
    director + year. We keep both as the description."""
    parts: list[str] = []
    alt = content.find("div", class_="description", recursive=False)
    if alt and alt.get_text(strip=True):
        parts.append(_clean(alt.get_text(" ", strip=True)))
    for mi in content.select(".more-info .description.mini_text-1"):
        text = _clean(mi.get_text(" ", strip=True))
        if text and text not in parts:
            parts.append(text)
    return " — ".join(parts) if parts else None


def _card_cycle(content: Tag) -> str | None:
    el = content.select_one(".text-alternative a")
    return _clean(el.get_text(strip=True)) if el and el.get_text(strip=True) else None


def _card_image(card: Tag) -> str | None:
    img = card.select_one(".header-card img[src]")
    src = img.get("src", "") if img else ""
    return _absolutize(src) if src else None


def parse_agenda(html: str) -> list[ScrapedEvent]:
    """Parse one Filmoteca weekly agenda page into ScrapedEvents.

    One ScrapedEvent per `.block-day .card`: title + detail URL from `.titl a`,
    local showtime from `.hour`, date from the GCal link, image from the card
    header, and the programming cycle as a free-form annotation. Every screening
    is category `film` (the venue does not sub-categorize); there is no per-session
    price to scrape (flat institutional rate)."""
    soup = BeautifulSoup(html, "html.parser")

    events: list[ScrapedEvent] = []
    for card in soup.select(".block-day .card"):
        title, source_url = _card_title_and_url(card)
        if not title or not source_url:
            continue
        start_date = _card_date(card)
        if start_date is None:
            continue  # no reliable date; skip rather than guess

        content = card.select_one(".content-card")
        cycle = _card_cycle(content) if content else None

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=_card_time(card),
                source_url=source_url,
                category_slugs=["film"],
                description=_card_description(content) if content else None,
                image_url=_card_image(card),
                external_id=source_url.rstrip("/").rsplit("/", 1)[-1] or None,
                annotations=[cycle] if cycle else [],
            )
        )

    return events


def _week_params(start: dt.date, weeks: int) -> list[str]:
    """`?w=` values (Mondays) for `weeks` consecutive weeks from `start`'s Monday."""
    monday = start - dt.timedelta(days=start.weekday())
    return [(monday + dt.timedelta(weeks=i)).isoformat() for i in range(weeks)]


class FilmotecaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        seen: set[tuple] = set()
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            for week in _week_params(dt.date.today(), _WEEKS_AHEAD):
                html = client.get(AGENDA_URL, params={"w": week}).text
                for ev in parse_agenda(html):
                    # The same film screens on several days / across week fetches;
                    # key the occurrence by film + date + time to dedup overlaps.
                    key = (ev.external_id, ev.start_date, ev.start_time)
                    if key in seen:
                        continue
                    seen.add(key)
                    events.append(ev)
        return events


register(
    scraper=FilmotecaScraper(),
    venue=VenueDefinition(
        slug="filmoteca",
        name="Filmoteca de Catalunya",
        city_slug="barcelona",
        address="Plaça de Salvador Seguí, 1-9, El Raval, 08001 Barcelona",
        site_url="https://www.filmoteca.cat",
        category_slugs=["film"],
        list_memberships=[
            ListMembership(list_slug="film"),
        ],
    ),
)
