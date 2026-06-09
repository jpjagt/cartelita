"""Teatre Romea scraper.

Data source: WordPress site, DOM scraping only. No usable JSON-LD for events.
The season page (https://www.teatreromea.cat/ca/season/) lists shows as
`.espectacle-query__item` cards. Each card carries:
  - title in `.title a`
  - detail URL in `a.image-container[href]`
  - show poster image in `.espectacle-query__item img[src]`
  - category discriminator in article CSS classes (dis_11=Teatre, dis_7=Comèdia,
    dis_17=Tragicomèdia, dis_4=Familiar/Kids)

Each show's detail page has a sticky sidebar with `.espectacle_funciones` listing
individual sessions as `<li>` items, each containing:
  - `.date` text: e.g. "dimecres, 10/06/2026 - 20:00"
  - `<a>` link to the ticket purchase page (external)

Price is not available on the Teatre Romea website — only a generic discount
policy is shown. Price = None for all events (systematically unavailable).

external_id: "{show-slug}@{date}T{HHMM}" — per-occurrence, since multiple
sessions share the same show slug.

Category mapping:
  dis_11 (Teatre)        → theater
  dis_7  (Comèdia)       → theater  (comedy is a sub-genre of theater)
  dis_17 (Tragicomèdia)  → theater
  dis_4  (Familiar)      → kids

Last verified: 2026-06-09
"""
from __future__ import annotations

import datetime as dt
import re

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

SEASON_URL = "https://www.teatreromea.cat/ca/season/"
BASE_URL = "https://www.teatreromea.cat"
VENUE_SLUG = "teatre-romea"

# CSS class → category slug mapping
# dis_4 = family/kids shows (e.g. "Post-clàssic amb Tortell Poltrona en família")
# dis_7 = Comèdia, dis_11 = Teatre, dis_17 = Tragicomèdia → all map to theater
_DIS_CATEGORY: dict[str, str] = {
    "dis_4": "kids",
    "dis_7": "theater",
    "dis_11": "theater",
    "dis_17": "theater",
}
_DEFAULT_CATEGORY = "theater"

# Genre annotation label for non-standard dis_ classes
_DIS_LABEL: dict[str, str] = {
    "dis_4": "Familiar",
    "dis_7": "Comèdia",
    "dis_17": "Tragicomèdia",
}

# Date format in session list: "dimecres, 10/06/2026 - 20:00"
_DATE_TIME_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{2}):(\d{2})")
# Show slug from URL: /ca/ex/<slug>/
_SLUG_RE = re.compile(r"/ca/ex/([^/?#]+)/?")


def _extract_show_slug(url: str) -> str | None:
    m = _SLUG_RE.search(url)
    return m.group(1) if m else None


def _parse_session_date(date_text: str) -> tuple[dt.date, dt.time] | None:
    """Parse 'dimecres, 10/06/2026 - 20:00' → (date, time)."""
    m = _DATE_TIME_RE.search(date_text)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hour, minute = int(m.group(4)), int(m.group(5))
    try:
        return dt.date(year, month, day), dt.time(hour, minute)
    except ValueError:
        return None


def _category_from_classes(classes: list[str]) -> str:
    for cls in classes:
        if cls in _DIS_CATEGORY:
            return _DIS_CATEGORY[cls]
    return _DEFAULT_CATEGORY


def parse_show(
    html: str,
    show_url: str,
    title: str,
    image_url: str | None,
    category_slug: str,
    annotations: list[str],
) -> list[ScrapedEvent]:
    """Parse one show detail page into per-session ScrapedEvents.

    The `.espectacle_funciones` element lists individual sessions with date/time
    and a ticket link. Each session becomes one ScrapedEvent with a unique
    external_id qualifying the show slug with date+time.
    """
    soup = BeautifulSoup(html, "html.parser")
    # The page has two `.espectacle_funciones` lists: one in the sticky sidebar
    # (.espectacle_side) and one in a hidden modal — both identical. Use only
    # the sidebar list to avoid emitting duplicate events.
    sidebar = soup.select_one(".espectacle_side .espectacle_funciones")
    if not sidebar:
        # Fallback to any espectacle_funciones (old layout or future change)
        sidebar = soup.select_one(".espectacle_funciones")
    if not sidebar:
        return []
    session_items = sidebar.select("li")

    show_slug = _extract_show_slug(show_url)
    events: list[ScrapedEvent] = []

    for li in session_items:
        date_el = li.select_one(".date")
        if not date_el:
            continue
        parsed = _parse_session_date(date_el.get_text(strip=True))
        if not parsed:
            continue
        session_date, session_time = parsed

        # external_id is per-occurrence: qualify show slug with date+time
        ext_id = (
            f"{show_slug}@{session_date.isoformat()}T{session_time.strftime('%H%M')}"
            if show_slug
            else None
        )

        events.append(
            ScrapedEvent(
                title=title,
                start_date=session_date,
                start_time=session_time,
                source_url=show_url,
                category_slugs=[category_slug],
                price=None,  # price not available on teatreromea.cat
                image_url=image_url,
                external_id=ext_id,
                annotations=list(annotations),  # copy to avoid sharing
            )
        )

    return events


def _parse_show_list(html: str) -> list[dict]:
    """Parse season page → list of show dicts with url, title, image, category, annotations."""
    soup = BeautifulSoup(html, "html.parser")
    shows: list[dict] = []

    for article in soup.select(".espectacle-query__item"):
        title_el = article.select_one(".title a")
        link_el = article.select_one("a.image-container")
        img_el = article.select_one("img")

        if not title_el or not link_el:
            continue

        title = title_el.get_text(strip=True)
        url = link_el.get("href", "")
        if not url:
            continue

        # Normalize relative URLs
        if url.startswith("/"):
            url = BASE_URL + url

        image_url = img_el.get("src") if img_el else None

        # Category from article classes
        classes = article.get("class", [])
        category = _category_from_classes(classes)

        # Genre annotation for non-standard dis_ classes (Comèdia, Tragicomèdia, Familiar)
        annotations: list[str] = []
        for cls in classes:
            if cls in _DIS_LABEL:
                annotations.append(_DIS_LABEL[cls])

        shows.append(
            {
                "title": title,
                "url": url,
                "image_url": image_url,
                "category": category,
                "annotations": annotations,
            }
        )

    return shows


def parse_agenda(
    season_html: str,
    show_htmls: dict[str, str],
) -> list[ScrapedEvent]:
    """Parse the season listing + per-show HTML into ScrapedEvents.

    Args:
        season_html: HTML of the season page (teatreromea.cat/ca/season/).
        show_htmls: Mapping of show URL → show detail page HTML.
    """
    shows = _parse_show_list(season_html)
    events: list[ScrapedEvent] = []

    for show in shows:
        url = show["url"]
        detail_html = show_htmls.get(url, "")
        if not detail_html:
            continue

        show_events = parse_show(
            html=detail_html,
            show_url=url,
            title=show["title"],
            image_url=show["image_url"],
            category_slug=show["category"],
            annotations=show["annotations"],
        )
        events.extend(show_events)

    return events


class TeatreRomeaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        season_html = httpx.get(SEASON_URL, follow_redirects=True, timeout=30).text
        shows = _parse_show_list(season_html)

        show_htmls: dict[str, str] = {}
        for show in shows:
            url = show["url"]
            show_htmls[url] = httpx.get(url, follow_redirects=True, timeout=30).text

        return parse_agenda(season_html, show_htmls)


register(
    scraper=TeatreRomeaScraper(),
    venue=VenueDefinition(
        slug="teatre-romea",
        name="Teatre Romea",
        city_slug="barcelona",
        address="C/ de l'Hospital, 51, 08001 Barcelona",
        site_url="https://www.teatreromea.cat",
        category_slugs=["theater", "kids"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
