"""Teatre Goya scraper.

Data sources
------------
Season list  : https://www.teatregoya.cat/ca/season/
               Six WordPress articles rendered with Isotope JS filter.
               Each card has title, detail URL, date range, and category
               classes (dis_11 = Teatre, dis_7 = Comèdia, dis_12 = Monòlegs).

Detail pages : https://www.teatregoya.cat/ca/ex/<slug>/
               Each show page contains a hidden buy-modal
               (#single_ex_buy_modal) rendered server-side in the HTML.
               The modal lists upcoming sessions as
               "<weekday>, DD/MM/YYYY - HH:MM" with a per-session ticket
               link: https://tickets.oneboxtds.com/teatregoya/select/<id>
               The ticket id is stable per occurrence and used as external_id.

Category map
------------
All genres (Teatre/Comèdia/Monòlegs) map to `theater`.
The dis_ class from the season page is kept as an annotation.

Price
-----
Not available on the venue website; ticket pricing is behind a Cloudflare-
protected third-party site (oneboxtds.com). All events have price=None.

External ID
-----------
Ticket session id from the buy-modal link, e.g. "2735825".  This is a
per-occurrence id (each session has its own id), so no date-qualification
is needed.

Sessions shown
--------------
The buy modal shows the next ~6–12 upcoming sessions per show. A
"Per a altres dates" fallback link appears when there are more. The scraper
emits exactly the sessions shown in the modal; older or far-future sessions
outside that window are not visible on the page.

Last verified: 2026-06-09
"""
from __future__ import annotations

import datetime as dt
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

SEASON_URL = "https://www.teatregoya.cat/ca/season/"
BASE_URL = "https://www.teatregoya.cat"
VENUE_SLUG = "teatre-goya"

# Season-page Isotope filter classes → annotation labels.
# All map to theater; the dis_ label is kept as an annotation.
_DIS_LABEL: dict[str, str] = {
    "dis_11": "Teatre",
    "dis_7": "Comèdia",
    "dis_12": "Monòlegs",
}

# Date+time in the buy modal: "divendres, 12/06/2026 - 22:30"
_SESSION_RE = re.compile(r"\d{2}/(\d{2})/(\d{4})\s*-\s*(\d{2}):(\d{2})")
# Full match including day-of-week prefix (unused but consumed):
_SESSION_FULL_RE = re.compile(
    r"(?:\w+,\s*)?"          # optional weekday + comma
    r"(\d{2})/(\d{2})/(\d{4})"  # DD/MM/YYYY
    r"\s*-\s*"
    r"(\d{2}):(\d{2})"      # HH:MM
)
# Ticket select URL: …/select/<id>?…
_TICKET_ID_RE = re.compile(r"/select/(\d+)")


def _parse_session_line(text: str) -> tuple[dt.date, dt.time] | None:
    """Parse 'divendres, 12/06/2026 - 22:30' → (date, time) or None."""
    m = _SESSION_FULL_RE.search(text)
    if not m:
        return None
    day, month, year, hour, minute = (int(x) for x in m.groups())
    try:
        return dt.date(year, month, day), dt.time(hour, minute)
    except ValueError:
        return None


def _parse_ticket_id(href: str) -> str | None:
    m = _TICKET_ID_RE.search(href)
    return m.group(1) if m else None


def _dis_class(classes: list[str]) -> str | None:
    for c in classes:
        if c in _DIS_LABEL:
            return c
    return None


def parse_show_detail(
    html: str,
    source_url: str,
    title: str,
    image_url: str | None,
    category_annotation: str | None,
) -> list[ScrapedEvent]:
    """Parse one show detail page into one ScrapedEvent per session.

    Reads the server-rendered buy modal (#single_ex_buy_modal) which lists
    upcoming sessions with dates, times, and per-session ticket IDs.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Prefer the h1 title from the detail page over the season-list title.
    h1 = soup.find("h1")
    if h1:
        t = h1.get_text(strip=True)
        if t:
            title = t

    # Description from the sinopsi block.
    sinopsi = soup.select_one("#sinopsi .entry-content")
    description = sinopsi.get_text(" ", strip=True) if sinopsi else None
    if description and len(description) > 500:
        description = description[:500].rstrip() + "…"

    # Poster image (may already be set from season page).
    if not image_url:
        poster = soup.select_one(".espectacle_basic_data img.poster")
        if poster:
            image_url = poster.get("src") or None

    # Parse sessions from the buy modal.
    modal = soup.find("id", id="single_ex_buy_modal") or soup.find(
        id="single_ex_buy_modal"
    )
    if not isinstance(modal, Tag):
        return []

    events: list[ScrapedEvent] = []
    for li in modal.select("li:not(.other_dates)"):
        date_span = li.find("span", class_="date")
        if not date_span:
            continue
        parsed = _parse_session_line(date_span.get_text(strip=True))
        if not parsed:
            continue
        session_date, session_time = parsed

        # Ticket session id from the "Comprar" link.
        link = li.find("a")
        href = link.get("href", "") if link else ""
        ticket_id = _parse_ticket_id(href)
        if not ticket_id:
            continue

        annotations: list[str] = []
        if category_annotation:
            annotations.append(category_annotation)

        events.append(
            ScrapedEvent(
                title=title,
                start_date=session_date,
                start_time=session_time,
                source_url=source_url,
                category_slugs=["theater"],
                price=None,
                description=description,
                image_url=image_url,
                external_id=ticket_id,
                annotations=annotations,
            )
        )

    return events


def parse_season_page(html: str) -> list[tuple[str, str, str | None, str | None]]:
    """Parse the season list page.

    Returns a list of (title, detail_url, image_url, dis_class_label) tuples
    for each show card.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for article in soup.select(".espectacle-query__item"):
        title_el = article.select_one(".title a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)

        url_el = article.select_one("a.image-container")
        if not url_el:
            continue
        detail_url = url_el.get("href", "")
        if not detail_url:
            continue

        img = article.select_one("img")
        image_url = img.get("src") if img else None

        classes = article.get("class", [])
        dc = _dis_class(classes)
        label = _DIS_LABEL.get(dc or "", None) if dc else None

        results.append((title, detail_url, image_url, label))
    return results


class TeatreGoyaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        season_html = httpx.get(SEASON_URL, follow_redirects=True, timeout=30).text
        shows = parse_season_page(season_html)

        events: list[ScrapedEvent] = []
        for title, detail_url, image_url, annotation in shows:
            detail_html = httpx.get(
                detail_url, follow_redirects=True, timeout=30
            ).text
            show_events = parse_show_detail(
                detail_html,
                source_url=detail_url,
                title=title,
                image_url=image_url,
                category_annotation=annotation,
            )
            events.extend(show_events)

        return events


register(
    scraper=TeatreGoyaScraper(),
    venue=VenueDefinition(
        slug="teatre-goya",
        name="Teatre Goya",
        city_slug="barcelona",
        address="C/ Joaquín Costa, 68, 08001 Barcelona",
        site_url="https://www.teatregoya.cat",
        category_slugs=["theater"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
        ],
    ),
)
