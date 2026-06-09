from __future__ import annotations

import datetime as dt
import re

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# La Poderosa (Gothic Quarter, Barcelona) — small grassroots dance / live-art
# space. Drupal site; no JSON-LD. The HOMEPAGE is the canonical event list (one
# .node-event.node-teaser card per event); /ca/programes is editorial text, not
# an agenda. Each teaser carries title, detail link, image, a `tipus` label, and
# an ISO date (single or start/end range). Price is never published (the venue
# runs on free / pay-what-you-want terms) so price is always None — see SOURCE.md.
HOME_URL = "https://lapoderosa.es/ca"
BASE_URL = "https://lapoderosa.es"
VENUE_SLUG = "la-poderosa"

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# La Poderosa is a dance / live-art house: every `tipus` label is movement /
# performance work, all mapped to `dance`. The raw label is preserved as an
# annotation so the performance/presentation/residency distinction is kept.
_DEFAULT_CATEGORY = "dance"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _clean_title(text: str) -> str:
    """Collapse whitespace and strip a dangling separator slash (e.g. 'NORMA PÉREZ /')."""
    t = _clean(text)
    return t.rstrip(" /").strip() or t


def _parse_iso(content: str | None) -> tuple[dt.date, dt.time | None] | None:
    """Parse a Drupal date `content` attr ('2026-07-17T19:00:00+02:00').

    Returns (date, time) where time is None for the all-day sentinel 00:00:00.
    """
    if not content:
        return None
    try:
        parsed = dt.datetime.fromisoformat(content)
    except ValueError:
        return None
    start_time = None if (parsed.hour == 0 and parsed.minute == 0) else parsed.time().replace(tzinfo=None)
    return parsed.date(), start_time


def _extract_slug(href: str) -> str | None:
    m = re.search(r"/event/([^/?#]+)", href)
    return m.group(1) if m else None


def parse_home(html: str) -> list[ScrapedEvent]:
    """Parse the La Poderosa homepage into ScrapedEvents (one per teaser card)."""
    soup = BeautifulSoup(html, "html.parser")
    events: list[ScrapedEvent] = []
    seen_ids: set[str] = set()

    for card in soup.select(".node-event.node-teaser"):
        title_el = card.select_one(".field-name-title-field h3 a")
        if not title_el:
            continue
        title = _clean_title(title_el.get_text(" "))
        if not title:
            continue

        href = title_el.get("href", "").strip()
        if not href:
            link = card.select_one("a[href*='/event/']")
            href = link.get("href", "").strip() if link else ""
        if not href:
            continue
        source_url = href if href.startswith("http") else BASE_URL + href
        slug = _extract_slug(href)

        # Date: single, else start-of-range.
        date_el = card.select_one(".date-display-single") or card.select_one(".date-display-start")
        parsed = _parse_iso(date_el.get("content") if date_el else None)
        if not parsed:
            continue
        start_date, start_time = parsed

        # Optional end of range.
        end_date = None
        end_el = card.select_one(".date-display-end")
        if end_el:
            end_parsed = _parse_iso(end_el.get("content"))
            if end_parsed:
                end_date = end_parsed[0]

        img_el = card.select_one(".field-name-field-img-event img")
        image_url = None
        if img_el:
            src = img_el.get("src", "").strip()
            if src:
                image_url = src if src.startswith("http") else BASE_URL + src

        tipus_el = card.select_one(".field-name-field-tipus-event .field-item")
        tipus = _clean(tipus_el.get_text(" ")) if tipus_el else None

        annotations: list[str] = []
        if tipus:
            annotations.append(tipus)

        date_str = start_date.isoformat()
        time_str = start_time.strftime("%H%M") if start_time else "0000"
        if slug:
            external_id = f"{slug}@{date_str}T{time_str}"
        else:
            external_id = f"{VENUE_SLUG}-{date_str}T{time_str}"
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                end_date=end_date,
                source_url=source_url,
                category_slugs=[_DEFAULT_CATEGORY],
                price=None,  # never published by this venue — see SOURCE.md
                image_url=image_url,
                external_id=external_id,
                annotations=annotations,
            )
        )
    return events


class LaPoderosaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        r = httpx.get(HOME_URL, headers=_HEADERS, follow_redirects=True, timeout=30)
        r.raise_for_status()
        return parse_home(r.text)


register(
    scraper=LaPoderosaScraper(),
    venue=VenueDefinition(
        slug="la-poderosa",
        name="La Poderosa",
        city_slug="barcelona",
        address="Gothic Quarter, Barcelona",
        site_url="https://lapoderosa.es/",
        category_slugs=["dance"],
        list_memberships=[
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
        ],
    ),
)
