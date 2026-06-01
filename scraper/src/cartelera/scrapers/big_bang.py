from __future__ import annotations
import datetime as dt
import re

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Big Bang Bar (El Raval, Barcelona) has a fully static weekly schedule — every
# week repeats the same programme. The homepage server-renders plain text that
# confirms the schedule, so we don't need to parse it: we hard-code the template
# and expand it into concrete dated occurrences for the next LOOKAHEAD_DAYS days.
#
# Friday/Saturday midnight DJ sessions are tagged `club`; everything else is `jazz`.
# DJ sessions start at midnight (00:00); the frontend groups 00:00–04:59 events
# under the previous calendar day so they appear as late-night of that evening.

SITE_URL = "https://bigbangbar.wixsite.com/bigbang"
VENUE_SLUG = "big-bang-bar"
LOOKAHEAD_DAYS = 14

# (weekday_int 0=Mon, title, hour, minute_or_None, category_slugs, annotations)
# hour=None → start_time=None (time unknown)
_WEEKLY: list[tuple[int, str, int | None, int | None, list[str], list[str]]] = [
    (0, "Big Bang Open Mic",    21,   0, ["jazz"],         ["Rock", "Blues", "Pop"]),
    (1, "Raval Music",          21,   0, ["jazz"],         []),
    (2, "Big Bang Open Mic",    20,  30, ["jazz"],         ["Rock", "Blues", "Pop"]),
    (3, "Big Bang Open Mic",    20,  30, ["jazz"],         ["Rock", "Blues", "Pop"]),
    (4, "Jam Session de Jazz",  21,   0, ["jazz"],         []),
    (4, "Dj Session",           0,    0,  ["club"],      []),
    (5, "New Orleans Jazz Jam", 21,   0, ["jazz"],         ["Concierto", "Jam Session"]),
    (5, "Dj Session",           0,    0,  ["club"],      []),
    (6, "Big Bang Open Mic",    20,   0, ["jazz"],         ["Rock", "Blues", "Pop"]),
]

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _title_slug(title: str) -> str:
    return _SLUG_RE.sub("-", title.lower()).strip("-")


def generate_events(today: dt.date | None = None) -> list[ScrapedEvent]:
    """Generate ScrapedEvents for the next LOOKAHEAD_DAYS days from today."""
    if today is None:
        today = dt.date.today()

    events: list[ScrapedEvent] = []
    for offset in range(LOOKAHEAD_DAYS):
        date = today + dt.timedelta(days=offset)
        weekday = date.weekday()  # 0=Monday … 6=Sunday
        for wd, title, hour, minute, cats, annotations in _WEEKLY:
            if wd != weekday:
                continue
            start_time = dt.time(hour, minute) if hour is not None else None
            ext_id = f"{VENUE_SLUG}-{date.isoformat()}-{_title_slug(title)}"
            events.append(
                ScrapedEvent(
                    title=title,
                    start_date=date,
                    start_time=start_time,
                    source_url=SITE_URL,
                    category_slugs=cats,
                    price="free",
                    external_id=ext_id,
                    annotations=annotations,
                )
            )
    return events


class BigBangBarScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return generate_events()


register(
    scraper=BigBangBarScraper(),
    venue=VenueDefinition(
        slug="big-bang-bar",
        name="Big Bang Bar",
        city_slug="barcelona",
        address="Carrer de la Botella, 7, El Raval, 08001 Barcelona",
        site_url="https://bigbangbar.wixsite.com/bigbang",
        category_slugs=["jazz", "club"],
        list_memberships=[
            ListMembership(list_slug="jazz", whitelist_category_slug="jazz"),
            ListMembership(list_slug="club", whitelist_category_slug="club"),
        ],
    ),
)
