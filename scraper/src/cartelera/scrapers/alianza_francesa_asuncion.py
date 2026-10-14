"""Alianza Francesa de Asunción — weekly "AF Cine" screenings, film cycles and
the occasional play, in its Sala Molière.

The site is WordPress + Modern Events Calendar (MEC). Its agenda page renders
the calendar client-side, but MEC exposes two machine-readable pieces we
combine (see alianza_francesa_asuncion_SOURCE.md):

1. `GET /wp-json/wp/v2/mec-events?per_page=50` — the event posts, newest
   first (id, link, publish date). It carries no event dates.
2. `GET <post link>?method=ical&id=<id>` — MEC's per-event iCalendar export:
   DTSTART/DTEND in UTC, SUMMARY, DESCRIPTION, CATEGORIES (the calendar's own
   category names), LOCATION, URL, ATTACH (poster).

Posts are published a few weeks ahead in monthly batches, so only the posts
published in the last RECENT_DAYS are fetched (one iCal request each) and
only occurrences from today on are emitted.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from zoneinfo import ZoneInfo

from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

SITE_URL = "https://alianzafrancesa.edu.py"
POSTS_URL = f"{SITE_URL}/wp-json/wp/v2/mec-events?per_page=50&_fields=id,link,date"
VENUE_SLUG = "alianza-francesa-asuncion"
TZ = ZoneInfo("America/Asuncion")
RECENT_DAYS = 150

# The calendar's own category names → our categories.
PROGRAMME = {"Cine": "film", "Teatro": "theater"}
# Category names that mark an item as not programme: talks/lecture cycles
# (often with a screening attached), the country fair of the Francophonie day.
NON_PROGRAMME = {"Charla", "Feria de países"}
# Category names that say nothing about the item's kind.
NEUTRAL = {"arte"}
# AF Asunción's own location (MEC stores the address only).
OWN_LOCATION = "Estigarribia 1039"


def _unescape(value: str) -> str:
    out = re.sub(r"\\([,;\\])", r"\1", value)
    return re.sub(r"\\[nN]", "\n", out)


def parse_ical(text: str) -> list[dict[str, str]]:
    """VEVENTs of an iCalendar body as {PROPERTY;PARAMS: raw value} dicts
    (folded lines joined; values still escaped)."""
    lines = re.sub(r"\r?\n[ \t]", "", text).splitlines()
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            current.setdefault(key, value)
    return events


def _prop(ev: dict[str, str], name: str) -> tuple[str, str] | None:
    """(params, value) of the first property called `name`."""
    for key, value in ev.items():
        prop, _, params = key.partition(";")
        if prop == name:
            return params, value
    return None


def _start(ev: dict[str, str]) -> tuple[dt.date, dt.time | None] | None:
    found = _prop(ev, "DTSTART")
    if not found:
        return None
    params, value = found
    if "VALUE=DATE" in params or len(value) == 8:
        return dt.datetime.strptime(value[:8], "%Y%m%d").date(), None
    if value.endswith("Z"):
        utc = dt.datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
        local = utc.astimezone(TZ)
    else:  # floating or TZID= local time: already wall-clock
        local = dt.datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    return local.date(), local.time().replace(tzinfo=None)


def categorize(names: list[str]) -> list[str]:
    if set(names) & NON_PROGRAMME:
        return []
    return list(dict.fromkeys(PROGRAMME[n] for n in names if n in PROGRAMME))


def parse_event(ical: str, post: dict, today: dt.date) -> ScrapedEvent | None:
    """The post's occurrence as a ScrapedEvent, or None when it isn't
    programme, is elsewhere, or is past."""
    vevents = parse_ical(ical)
    if not vevents:
        return None
    ev = vevents[0]
    start = _start(ev)
    if start is None or start[0] < today:
        return None
    names = [n.strip() for n in _unescape((_prop(ev, "CATEGORIES") or ("", ""))[1]).split(",") if n.strip()]
    cats = categorize(names)
    if not cats:
        return None
    location = _unescape((_prop(ev, "LOCATION") or ("", ""))[1])
    if location and OWN_LOCATION not in location:
        return None
    title = _unescape((_prop(ev, "SUMMARY") or ("", ""))[1]).strip()
    if not title:
        return None
    description = _unescape((_prop(ev, "DESCRIPTION") or ("", ""))[1]).strip()
    url = (_prop(ev, "URL") or ("", post.get("link") or ""))[1] or post.get("link")
    image = _prop(ev, "ATTACH")
    return ScrapedEvent(
        title=title,
        start_date=start[0],
        start_time=start[1],
        source_url=url,
        category_slugs=cats,
        description=re.sub(r"\n{3,}", "\n\n", description) or None,
        image_url=image[1] if image else None,
        external_id=str(post["id"]),
        annotations=[n for n in names if n not in PROGRAMME and n not in NEUTRAL],
    )


def recent_posts(posts: list[dict], today: dt.date) -> list[dict]:
    """Posts published within RECENT_DAYS (events are posted weeks ahead)."""
    cutoff = today - dt.timedelta(days=RECENT_DAYS)
    return [p for p in posts if dt.date.fromisoformat(p["date"][:10]) >= cutoff]


class AlianzaFrancesaAsuncionScraper:
    venue_slug = VENUE_SLUG

    def scrape(self, today: dt.date | None = None) -> list[ScrapedEvent]:
        today = today or dt.datetime.now(TZ).date()
        headers = CARTELITA_BROWSER_HEADERS
        posts = json.loads(fetch(POSTS_URL, headers=headers))
        events: list[ScrapedEvent] = []
        for post in recent_posts(posts, today):
            ical = fetch(f"{post['link']}?method=ical&id={post['id']}", headers=headers)
            ev = parse_event(ical, post, today)
            if ev is not None:
                events.append(ev)
        return events


register(
    scraper=AlianzaFrancesaAsuncionScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Alianza Francesa de Asunción",
        city_slug="asuncion",
        address="Mcal. Estigarribia 1039 c/ EE.UU., Asunción",
        site_url=SITE_URL,
        instagram_url="https://www.instagram.com/alianzafrancesaasu",
        category_slugs=["film", "theater"],
        list_memberships=[
            ListMembership(list_slug="film", whitelist_category_slug="film"),
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
        ],
    ),
)
