from __future__ import annotations

import datetime as dt
import re

from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.scrapers._nl_common import get, infer_year
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# Toffler (Weena-Zuid, Rotterdam) — techno/house club in a former pedestrian
# tunnel. An Elementor WordPress site; `/club/` is a hand-edited "Upcoming
# events" block: per night a container of text widgets — the date ("Friday
# 16.10", no year), the title ("TOFFLER Presents …") and the line-up — plus a
# "tickets" button to the Paylogic shop. ~8 nights ahead. See
# toffler_SOURCE.md.
#
# Every night is club. No per-night time or price on the site (the FAQ's
# "Doors open at 23:00 till 05:00. Please always check the event opening
# times" is a house default, not a per-event statement → time None); prices
# live on Paylogic's JS shop → None.
CLUB_URL = "https://www.toffler.nl/club/"
VENUE_SLUG = "toffler"

_DATE = re.compile(r"^\s*[A-Za-z]+day\s+(\d{1,2})\.(\d{1,2})\s*$")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_club(html: str, today: dt.date) -> list[ScrapedEvent]:
    """`/club/` → one club ScrapedEvent per night (pure; no network)."""
    soup = BeautifulSoup(html, "html.parser")
    events: dict[str, ScrapedEvent] = {}
    for widget in soup.select(".elementor-widget-text-editor"):
        m = _DATE.match(widget.get_text(" "))
        if not m:
            continue
        date = infer_year(int(m.group(2)), int(m.group(1)), today)
        if date is None:
            continue
        container = widget.parent
        texts = [
            _clean(w.get_text(" "))
            for w in container.select(":scope > .elementor-widget-text-editor")
        ]
        texts = [t for t in texts if t and not _DATE.match(t)]
        if not texts:
            continue
        title = texts[0]
        lineup = texts[1] if len(texts) > 1 else None
        external_id = f"toffler@{date.isoformat()}"
        if external_id in events:
            external_id = f"{external_id}#{len(events)}"
        events[external_id] = ScrapedEvent(
            title=title,
            start_date=date,
            source_url=CLUB_URL,
            category_slugs=["club"],
            description=f"Line-up: {lineup}" if lineup else None,
            external_id=external_id,
            annotations=[],
        )
    return list(events.values())


class TofflerScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return parse_club(get(CLUB_URL), dt.date.today())


register(
    scraper=TofflerScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Toffler",
        city_slug="rotterdam",
        address="Weena-Zuid 33, 3012 NH Rotterdam",
        site_url="https://www.toffler.nl/",
        instagram_url="https://www.instagram.com/tofflerrotterdam",
        category_slugs=["club"],
        list_memberships=[
            ListMembership(list_slug="club", whitelist_category_slug="club"),
        ],
    ),
)
