from __future__ import annotations
import datetime as dt
import html as html_module
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Casa Batlló "Magical Nights" (Passeig de Gràcia, Barcelona) — live rooftop
# concerts on Gaudí's building: a guided visit + a glass of cava + a live concert
# on the terrace. The programme is *not* classical strings as one might expect: the
# 2026 lineup is contemporary/world live music — soul, funk, jazz, swing, rumba,
# flamenco, bossa, boleros, pop, rock (the venue's own banner reads "SOUL, JAZZ,
# FLAMENCO, RUMBA..."). See casa_batllo_SOURCE.md for the full category note.
#
# Data lives in two layers, both server-rendered (no JS needed):
#   1. The Magic Nights page (`AGENDA_URL`) carries the *roster* — a
#      `<ul class="artists-list">` with one `<li class="artists-item">` per act,
#      each holding the artist name, its genre string, and a link to the artist's
#      own page. This page lists NO dates.
#   2. Each artist page carries that act's dated concert *occurrences* in a
#      `[data-module="event-artist"]` section: `<ul class="cb-events__list__month">`
#      grouped by month, each `<li class="cb-event-item">` is one concert with a
#      date ("Tuesday 9"), a time ("20:00 h") and a ticket link whose `event_id`
#      query param is the stable per-occurrence id.
#
# So `scrape()` is 1 + N requests (roster + one per artist). One ScrapedEvent per
# concert occurrence; external_id is the `event_id` (already per-occurrence).
AGENDA_URL = "https://www.casabatllo.es/en/magic-nights"
BASE_URL = "https://www.casabatllo.es"
VENUE_SLUG = "casa-batllo"

# Every act here is contemporary/world live music. None is classical; many lean
# jazz (jazz/swing/blues/boogaloo/bolero/bossa/samba). We map to `jazz` as the
# nearest existing top-level music category (see SOURCE.md — a `live-music`
# category is the truthful fit and is recommended). The granular per-act genre is
# always preserved verbatim in `annotations`.
VENUE_CATEGORY = "jazz"

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4,
    "saturday": 5, "sunday": 6,
}
# "Tuesday 9" → weekday name + day-of-month.
_DATE_RE = re.compile(r"([A-Za-z]+)\s+(\d{1,2})")
_HOUR_RE = re.compile(r"(\d{1,2}):(\d{2})")
_EVENT_ID_RE = re.compile(r"event_id=(\d+)")


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").strip()


def _absolutize(url: str) -> str:
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE_URL + url
    return url


def _resolve_year(month: int, day: int, weekday: int, today: dt.date) -> int:
    """Find the year (today's or one of the next two) whose `month/day` falls on the
    stated `weekday`. The page prints the weekday but no year; the weekday pins it
    unambiguously to a concrete year, which is more robust than a bare
    next-occurrence heuristic across a year boundary."""
    for year in (today.year, today.year + 1, today.year + 2):
        try:
            candidate = dt.date(year, month, day)
        except ValueError:
            continue
        if candidate.weekday() == weekday and candidate >= today:
            return year
    # Fall back: month/day in this year or next, ignoring the weekday check.
    candidate = dt.date(today.year, month, day)
    return today.year if candidate >= today else today.year + 1


def parse_agenda(html: str) -> list[tuple[str, str, str]]:
    """Parse the Magic Nights roster → one `(name, genre, detail_url)` per artist.

    Reads `<ul class="artists-list"> <li class="artists-item">`: the name from
    `.artist-title label`, the genre from `.artist-title span`, the per-artist page
    URL from `a.artist-content`. This page carries no dates — the concert
    occurrences live on each artist's page (see `parse_artist_events`)."""
    soup = BeautifulSoup(html, "html.parser")
    artists: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for li in soup.select("ul.artists-list li.artists-item"):
        name_el = li.select_one(".artist-title label")
        genre_el = li.select_one(".artist-title span")
        link = li.select_one("a.artist-content")
        if not name_el or not link:
            continue
        name = _clean(name_el.get_text(" ", strip=True))
        genre = _clean(genre_el.get_text(" ", strip=True)) if genre_el else ""
        href = _absolutize(link.get("href", ""))
        if not name or not href or href in seen:
            continue
        seen.add(href)
        artists.append((name, genre, href))
    return artists


def parse_artist_events(
    html: str,
    *,
    artist_name: str,
    genre: str,
    source_url: str,
    today: dt.date | None = None,
) -> list[ScrapedEvent]:
    """Parse one artist's page → one ScrapedEvent per dated concert occurrence.

    The `[data-module="event-artist"]` section groups occurrences by month
    (`<ul class="cb-events__list__month">` with a `<label>` month name); each
    `<li class="cb-event-item">` is one concert. Items carrying the `disable` class
    (past/unavailable dates, no ticket link) are skipped. The `event_id` from the
    ticket link is the per-occurrence `external_id`."""
    today = today or dt.date.today()
    soup = BeautifulSoup(html, "html.parser")

    events: list[ScrapedEvent] = []
    annotations = [genre] if genre and genre.lower() != "artist to be defined" else []

    for ul in soup.select("ul.cb-events__list__month"):
        month_el = ul.select_one("label")
        month_name = _clean(month_el.get_text(strip=True)).lower() if month_el else ""
        month = _MONTHS.get(month_name)
        if month is None:
            continue

        for li in ul.select("li.cb-event-item"):
            classes = li.get("class", [])
            if "disable" in classes:
                continue  # past/unavailable date: no ticket link, no event_id

            link = li.select_one("a.cb-btn")
            href = link.get("href", "") if link else ""
            id_match = _EVENT_ID_RE.search(href)
            if not id_match:
                continue  # no occurrence id → not a bookable concert
            event_id = id_match.group(1)

            date_el = li.select_one(".event-datetime__date")
            date_match = _DATE_RE.search(date_el.get_text(" ", strip=True)) if date_el else None
            if not date_match:
                continue
            weekday = _WEEKDAYS.get(date_match.group(1).lower())
            day = int(date_match.group(2))
            if weekday is None:
                continue
            year = _resolve_year(month, day, weekday, today)
            try:
                start_date = dt.date(year, month, day)
            except ValueError:
                continue

            hour_el = li.select_one(".event-datetime__hour")
            hour_match = _HOUR_RE.search(hour_el.get_text(strip=True)) if hour_el else None
            start_time: dt.time | None = None
            if hour_match:
                hh, mm = int(hour_match.group(1)), int(hour_match.group(2))
                if 0 <= hh < 24 and 0 <= mm < 60:
                    start_time = dt.time(hh, mm)

            events.append(
                ScrapedEvent(
                    title=artist_name,
                    start_date=start_date,
                    start_time=start_time,
                    source_url=source_url,
                    category_slugs=[VENUE_CATEGORY],
                    # No flat public price: Magic Nights is a visit+cava+concert
                    # bundle priced by day/time in the ticketing flow, and the only
                    # number on the page is a "-20€ residents" discount (skipped per
                    # the price convention). → None.
                    price=None,
                    external_id=event_id,  # already per-occurrence (unique per concert)
                    annotations=list(annotations),
                )
            )

    return events


class CasaBatlloScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        today = dt.date.today()
        with httpx.Client(
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (cartelera scraper)"},
        ) as client:
            agenda_html = client.get(AGENDA_URL).text
            artists = parse_agenda(agenda_html)

            events: list[ScrapedEvent] = []
            seen_ids: set[str] = set()
            for name, genre, url in artists:
                artist_html = client.get(url).text
                for ev in parse_artist_events(
                    artist_html,
                    artist_name=name,
                    genre=genre,
                    source_url=url,
                    today=today,
                ):
                    # Guard against an event_id appearing on two artist pages
                    # (the upsert raises on a duplicate within one batch).
                    if ev.external_id in seen_ids:
                        continue
                    seen_ids.add(ev.external_id)
                    events.append(ev)
        return events


register(
    scraper=CasaBatlloScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Casa Batlló — Magical Nights",
        city_slug="barcelona",
        address="Passeig de Gràcia, 43, L'Eixample, 08007 Barcelona",
        site_url="https://www.casabatllo.es",
        category_slugs=[VENUE_CATEGORY],
        list_memberships=[
            ListMembership(list_slug="jazz"),
        ],
    ),
)
