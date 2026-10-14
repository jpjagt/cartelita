"""Uitagenda Rotterdam (Rotterdam Festivals' city agenda) — a MULTI-VENUE,
WHITELIST source for Rotterdam theatre venues that have no better own feed.

See uitagenda_rotterdam_SOURCE.md for the field map, the genre/curation rules
and every exclusion with its reason.

Data: the agenda's own JSON back-end (Umbraco), two calls per run:

- `GET /umbraco/api/Entity/GetProductions?id=1083&pageSize=6000&culture=nl-NL
  &p=1&genre=theater&genre=cabaret&genre=dans-en-ballet&genre=jeugdtheater
  &genre=musical-of-show&genre=opera` — every production in the agenda's
  "Theater" genre tree (~1100 items, ~12 MB). Repeated `genre` values are
  OR-ed; the parent `theater` value on its own only matches the "Toneel"
  sub-genre, so each sub-genre must be listed.
- `GET ...GetProductions?id=17488&pageSize=6000&culture=nl-NL&p=1` — the
  agenda's own "Dans in Rotterdam" landing page (~150 items, ~1 MB): the set
  of items the agenda itself classifies as dance.
- `GET ...GetProductions?id=<location id>` for the two single-discipline
  houses (Mooi Weer, Hofplein; ~0.5 MB each): their genre-less items, which
  the genre-filtered call cannot return.

Each item is one production-DAY (`date` is ISO, `key` = "dd-mm-yyyy-hhmm");
`dates[]` lists every session of the production (no year), from which we take
the same-day sessions as `start_times`. The item's own `genres[]` only names
TOP-level genres (sub-genres are invisible), hence the dance landing call.
"""
from __future__ import annotations

import datetime as dt
import re

import httpx

from cartelera.scrapers import register_source
from cartelera.types import (
    ListMembership,
    ScrapedEvent,
    SourceDefinition,
    VenueDefinition,
)

SOURCE_SLUG = "uitagenda-rotterdam"
BASE_URL = "https://www.uitagendarotterdam.nl"
API_URL = f"{BASE_URL}/umbraco/api/Entity/GetProductions"
USER_AGENT = "Mozilla/5.0 (compatible; Cartelita (+https://cartelita.july.dev))"

AGENDA_PAGE_ID = 1083  # the /agenda/ page
DANCE_PAGE_ID = 17488  # the /ontdek/dans-in-rotterdam/ landing page
# The "Theater" genre tree (filterSetup.genres in the API response).
THEATER_GENRES = [
    "theater",
    "cabaret",
    "dans-en-ballet",
    "jeugdtheater",
    "musical-of-show",
    "opera",
]

# Uitagenda location id -> our venue slug. THE WHITELIST: only these locations'
# items are emitted; everything else in the feed is ignored. Ids are the
# agenda's Umbraco location nodes (title in the comment).
LOCATION_VENUES: dict[int, str] = {
    49531: "theater-rotterdam",  # TR25 Schouwburg (Schouwburgplein 25)
    49401: "theater-rotterdam",  # TR8 William Boothlaan (ex-Ro Theater / Witte de With)
    49729: "theater-walhalla",  # Kantine Walhalla (Veerlaan 11)
    49658: "theater-walhalla",  # Theater Walhalla (Sumatraweg 9)
    49352: "theater-walhalla",  # Werkplaats Walhalla (Tolhuisstraat 105)
    49556: "mooi-weer",  # Theater Mooi Weer
    49376: "hofplein",  # Jeugdtheater Hofplein
}

# A youth theatre: everything it programmes is for children/families.
YOUTH_VENUES = {"hofplein"}

# Single-discipline theatre houses: an item the agenda left WITHOUT any genre
# (so it is missing from the genre-filtered call) is still part of their stage
# programme. Their location pages are fetched too, and genre-less items there
# count as theater. (At Theater Rotterdam / Walhalla genre-less items include
# concerts and quizzes, so there they are dropped.) location id -> venue slug.
SINGLE_DISCIPLINE_LOCATIONS = {49556: "mooi-weer", 49376: "hofplein"}

# Top-level genres that mark an item as NOT part of the stage programme
# (dinner shows/food, workshops/courses, events: tours, talks, markets…,
# exhibitions). An item carrying any of them is dropped.
EXCLUDED_GENRES = {"culinair", "workshop", "evenementen", "expo"}

# The Theater Rotterdam feed uses 07:00 as a "time not set" placeholder (e.g.
# a production's first day at 07:00, every other day at 20:00).
_PLACEHOLDER_TIME = dt.time(7, 0)

_NL_MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}
_SHORT_DATE_RE = re.compile(r"(\d{1,2})\s+([a-z]{3})", re.I)
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")
_AGE_RE = re.compile(r"^\d+([.,]\d+)?\+")


def _time(text: str | None) -> dt.time | None:
    m = _TIME_RE.search(text or "")
    if not m:
        return None
    t = dt.time(int(m.group(1)), int(m.group(2)))
    return None if t == _PLACEHOLDER_TIME else t


def _end_time(text: str | None) -> dt.time | None:
    times = _TIME_RE.findall(text or "")
    if len(times) < 2:
        return None
    return dt.time(int(times[1][0]), int(times[1][1]))


def _day_month(short: str) -> tuple[int, int] | None:
    m = _SHORT_DATE_RE.search(short or "")
    if not m or m.group(2).lower() not in _NL_MONTHS:
        return None
    return int(m.group(1)), _NL_MONTHS[m.group(2).lower()]


def _title(item: dict) -> str:
    """The agenda splits a trailing "(…)" or "/ 8+" off the title into
    `ageIndication` ("Carmen (must die)" -> "Carmen" + "must die"; "Dag poes /
    4+" -> "Dag poes /" + "4+"). Re-join it the way the production page shows
    it."""
    title = " ".join((item.get("title") or "").split())
    age = " ".join((item.get("ageIndication") or "").split())
    if not age:
        return title
    if title.endswith(("/", "|")):
        return f"{title} {age}"
    return f"{title} ({age})"


def _is_kids_age(age: str | None) -> bool:
    """A source-stated age indication like "4+" / "1,5+" under 12."""
    m = _AGE_RE.match((age or "").strip())
    if not m:
        return False
    return float(m.group(0).rstrip("+").replace(",", ".")) < 12


def _sessions(item: dict, day: dt.date) -> list[dict]:
    loc = (item.get("location") or {}).get("title")
    out = []
    for d in item.get("dates") or []:
        if _day_month(d.get("dateBeautifiedShort", "")) != (day.day, day.month):
            continue
        if loc and d.get("location") and d["location"] != loc:
            continue
        out.append(d)
    return out


def _abs(path: str | None) -> str | None:
    if not path:
        return None
    return path if path.startswith("http") else BASE_URL + path


def _same_show(a: dict, b: dict) -> bool:
    """Two feeders (the venue's own feed and a ticketing feed) sometimes enter
    the same show twice at the same hall+time under slightly different titles
    ("Christmas Inc, een Winstgevende Kerstmusical" / "Christmas Inc - een
    Winstgevende Kerstmusical"). Treat items at the same location and start as
    duplicates when their titles share the first word (lowercased) — two
    unrelated shows starting together in one hall don't."""
    def first(it: dict) -> str:
        words = re.findall(r"\w+", (it.get("title") or "").lower())
        return words[0] if words else ""
    return first(a) == first(b) and _overlap(a, b) >= 0.5


def _overlap(a: dict, b: dict) -> float:
    wa = set(re.findall(r"\w+", (a.get("title") or "").lower()))
    wb = set(re.findall(r"\w+", (b.get("title") or "").lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def categorize(item: dict, venue_slug: str, dance_ids: set[int]) -> list[str] | None:
    """Category slugs from the agenda's own genre structure, or None to drop
    the item. Never from the title."""
    genres = {g.get("key") for g in item.get("genres") or []}
    if genres & EXCLUDED_GENRES:
        return None
    cats = ["dance"] if item["id"] in dance_ids else ["theater"]
    if (
        venue_slug in YOUTH_VENUES
        or "kids" in genres
        or _is_kids_age(item.get("ageIndication"))
    ):
        cats.append("kids")
    return cats


def _items(data: dict) -> list[dict]:
    return (data.get("pagedList") or {}).get("items") or []


def parse_productions(
    data: dict, dance_ids: set[int], location_pages: list[dict] | tuple[dict, ...] = (),
) -> list[ScrapedEvent]:
    """Pure: the theater-genre GetProductions response + the dance landing's
    item ids (+ the single-discipline venues' location-page responses) -> one
    ScrapedEvent per whitelisted production-day."""
    items = list(_items(data))
    seen = {it["id"] for it in items}
    for page in location_pages:
        for it in _items(page):
            loc_id = (it.get("location") or {}).get("id")
            if loc_id in SINGLE_DISCIPLINE_LOCATIONS and not it.get("genres") and it["id"] not in seen:
                seen.add(it["id"])
                items.append(it)
    kept: list[tuple[dict, ScrapedEvent]] = []
    for item in items:
        loc = item.get("location") or {}
        venue_slug = LOCATION_VENUES.get(loc.get("id"))
        if not venue_slug:
            continue
        cats = categorize(item, venue_slug, dance_ids)
        if cats is None:
            continue
        start = dt.datetime.fromisoformat(item["date"])
        day = start.date()
        sessions = _sessions(item, day)
        times = sorted({t for t in (_time(s.get("timeBeautified")) for s in sessions) if t})
        if not times and (t := _time(item["date"][11:16])):
            times = [t]
        end_time = _end_time(sessions[0].get("timeBeautified")) if len(sessions) == 1 else None
        soldout = all(s.get("soldout") for s in sessions) if sessions else item.get("soldout")
        price = "sold-out" if soldout else None
        ev = ScrapedEvent(
            title=_title(item),
            start_date=day,
            start_time=times[0] if times else None,
            start_times=times if len(times) > 1 else [],
            end_time=end_time,
            source_url=_abs(item.get("url")) or f"{BASE_URL}/agenda/",
            category_slugs=cats,
            price=price,
            description=(item.get("textShort") or None),
            image_url=_abs(item.get("image")),
            external_id=f"{item['parentId']}@{item['key']}",
            venue_slug=venue_slug,
        )
        dupe = next(
            (
                i for i, (other, oev) in enumerate(kept)
                if oev.venue_slug == venue_slug
                and other["location"]["id"] == loc["id"]
                and other["date"] == item["date"]
                and _same_show(other, item)
            ),
            None,
        )
        if dupe is not None:
            continue
        kept.append((item, ev))
    return [ev for _, ev in kept]


def dance_ids(data: dict) -> set[int]:
    return {it["id"] for it in _items(data)}


def _get(client: httpx.Client, page_id: int, genres: list[str] | None = None) -> dict:
    params: list[tuple[str, str | int]] = [
        ("id", page_id), ("pageSize", 6000), ("culture", "nl-NL"), ("p", 1),
    ]
    params += [("genre", g) for g in genres or []]
    resp = client.get(API_URL, params=params)
    resp.raise_for_status()
    return resp.json()


class UitagendaRotterdamScraper:
    def scrape(self) -> list[ScrapedEvent]:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=120, follow_redirects=True
        ) as client:
            theater = _get(client, AGENDA_PAGE_ID, THEATER_GENRES)
            dance = _get(client, DANCE_PAGE_ID)
            locations = [_get(client, loc_id) for loc_id in SINGLE_DISCIPLINE_LOCATIONS]
        return parse_productions(theater, dance_ids(dance), locations)


register_source(
    scraper=UitagendaRotterdamScraper(),
    source=SourceDefinition(
        slug=SOURCE_SLUG,
        name="Uitagenda Rotterdam",
        venues=[
            VenueDefinition(
                slug="theater-rotterdam",
                name="Theater Rotterdam",
                city_slug="rotterdam",
                address="Schouwburgplein 25, 3012 CL Rotterdam",
                site_url="https://www.theaterrotterdam.nl",
                category_slugs=["theater", "dance", "kids"],
                list_memberships=[
                    ListMembership(list_slug="theater", whitelist_category_slug="theater"),
                    ListMembership(list_slug="dance", whitelist_category_slug="dance"),
                    ListMembership(list_slug="kids", whitelist_category_slug="kids"),
                ],
            ),
            VenueDefinition(
                slug="theater-walhalla",
                name="Theater Walhalla",
                city_slug="rotterdam",
                address="Veerlaan 11, 3072 AN Rotterdam",
                site_url="https://www.theaterwalhalla.nl",
                category_slugs=["theater", "dance", "kids"],
                list_memberships=[
                    ListMembership(list_slug="theater", whitelist_category_slug="theater"),
                    ListMembership(list_slug="dance", whitelist_category_slug="dance"),
                    ListMembership(list_slug="kids", whitelist_category_slug="kids"),
                ],
            ),
            VenueDefinition(
                slug="mooi-weer",
                name="Theater Mooi Weer",
                city_slug="rotterdam",
                address="Willem Buytewechstraat 36-40, 3024 BN Rotterdam",
                site_url="https://www.theatermooiweer.nl",
                category_slugs=["theater"],
                list_memberships=[
                    ListMembership(list_slug="theater", whitelist_category_slug="theater"),
                ],
            ),
            VenueDefinition(
                slug="hofplein",
                name="Jeugdtheater Hofplein",
                city_slug="rotterdam",
                address="Benthemplein 13, 3032 CC Rotterdam",
                site_url="https://jeugdtheaterhofplein.nl",
                category_slugs=["theater", "kids"],
                list_memberships=[
                    ListMembership(list_slug="theater", whitelist_category_slug="theater"),
                    ListMembership(list_slug="kids", whitelist_category_slug="kids"),
                ],
            ),
        ],
    ),
)
