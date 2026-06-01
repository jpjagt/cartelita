from __future__ import annotations
import datetime as dt
import html as html_module
import json
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent

# The list view renders rich article cards (title, price, genre tags, detail
# link) for BOTH the Concerts and Disco sections in one page — far more complete
# than the JSON-LD (which omits price and category). We parse the article cards
# as the primary source and use the page's JSON-LD only to recover clean ISO
# start/end datetimes, keyed by detail URL.
AGENDA_URL = "https://jamboreejazz.com/agenda/llista/"
BASE_URL = "https://jamboreejazz.com"
VENUE_SLUG = "jamboree"

# Jamboree's club/disco nights are tagged "+18" (an age rating, used here as the
# section discriminator); everything else is a jazz concert. The other tags are
# musical genres kept as free-form annotations.
CLUB_TAG = "+18"


def _strip_html_entities(text: str) -> str:
    unescaped = html_module.unescape(text)
    return BeautifulSoup(unescaped, "html.parser").get_text(separator=" ", strip=True)


# The site emits local (Barcelona) wall-clock time; we keep the naive local time
# and drop the offset. If the source ever switches to UTC, this assumption breaks.
def _parse_iso(value: str) -> tuple[dt.date, dt.time | None]:
    value = re.sub(r"[+-]\d{2}:\d{2}$", "", value).rstrip("Z")
    if "T" in value:
        parsed = dt.datetime.fromisoformat(value)
        return parsed.date(), parsed.time()
    return dt.date.fromisoformat(value), None


def _normalize_url(url: str) -> str:
    url = url.split("?")[0].rstrip("/")
    if url.startswith("/"):
        url = BASE_URL + url
    return url


def _extract_external_id(url: str) -> str | None:
    m = re.search(r"/esdeveniment/([^/?#]+)", url)
    return m.group(1) if m else None


def _jsonld_times_by_url(soup: BeautifulSoup) -> dict[str, tuple]:
    """Map normalized detail URL -> (start_date, start_time, end_date, end_time)
    from the page's JSON-LD Event list, applying the all-day-sentinel rule."""
    times: dict[str, tuple] = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            blob = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if not (isinstance(blob, list) and blob and blob[0].get("@type") == "Event"):
            continue
        for item in blob:
            if item.get("@type") != "Event" or not item.get("url"):
                continue
            raw_start = item.get("startDate", "")
            if not raw_start:
                continue
            try:
                start_date, start_time = _parse_iso(raw_start)
            except (ValueError, AttributeError):
                continue
            end_date = end_time = None
            if item.get("endDate"):
                try:
                    end_date, end_time = _parse_iso(item["endDate"])
                except (ValueError, AttributeError):
                    pass
            # WordPress/Events-Calendar all-day sentinel = "time not set".
            if start_time == dt.time(0, 0) and end_time == dt.time(23, 59, 59):
                start_time = end_time = None
            times[_normalize_url(item["url"])] = (start_date, start_time, end_date, end_time)
    return times


def _article_tags(article: Tag) -> list[str]:
    return [a.get_text(strip=True) for a in article.select('a[href*="/tag/"]') if a.get_text(strip=True)]


def _article_title_and_url(article: Tag) -> tuple[str | None, str | None]:
    for a in article.select('a[href*="esdeveniment"]'):
        text = a.get_text(strip=True)
        if text:
            return text, _normalize_url(a.get("href", ""))
    # No titled link: still capture the URL (image/button link) if present.
    any_link = article.select_one('a[href*="esdeveniment"]')
    return None, (_normalize_url(any_link.get("href", "")) if any_link else None)


def parse_agenda(html: str) -> list[ScrapedEvent]:
    """Parse the Jamboree list-view agenda into ScrapedEvents.

    Primary source is the per-event ``<article>`` card (title, price, genre tags,
    detail link); JSON-LD supplies clean ISO datetimes. Category is derived from
    tags: a ``+18`` tag marks a club/disco night, otherwise it's a jazz concert.
    """
    soup = BeautifulSoup(html, "html.parser")
    times_by_url = _jsonld_times_by_url(soup)

    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for article in soup.select("article"):
        title, source_url = _article_title_and_url(article)
        if not title or not source_url:
            continue
        if source_url in seen:
            continue
        seen.add(source_url)

        tags = _article_tags(article)
        is_club = CLUB_TAG in tags
        category = "club" if is_club else "jazz"
        # Annotations: the genre tags, minus the +18 age-rating discriminator.
        annotations = [t for t in tags if t != CLUB_TAG]

        price_el = article.select_one(".preu-normal")
        price: str | None = None
        if price_el and price_el.get_text(strip=True):
            price = price_el.get_text(strip=True).replace(" ", "")
        elif "sold out" in article.get_text(" ", strip=True).lower():
            price = "s.o."

        times = times_by_url.get(source_url)
        if not times:
            continue  # no reliable date from JSON-LD; skip rather than guess
        start_date, start_time, end_date, end_time = times

        recurrence_hint = "every Monday" if "jam session" in title.lower() else None

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                end_date=end_date,
                end_time=end_time,
                source_url=source_url,
                category_slugs=[category],
                price=price,
                image_url=None,
                external_id=_extract_external_id(source_url),
                recurrence_hint=recurrence_hint,
                annotations=annotations,
            )
        )

    return events


class JamboreeScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        html = httpx.get(AGENDA_URL, follow_redirects=True, timeout=30).text
        return parse_agenda(html)


register(JamboreeScraper())
