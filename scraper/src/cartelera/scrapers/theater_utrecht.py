from __future__ import annotations

import datetime as dt
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.scrapers import _cre8ion as c8
from cartelera.types import (
    ListMembership,
    ScrapedEvent,
    ScrapedTranslation,
    VenueDefinition,
)

# Theater Utrecht — a city theatre company with its own house (Boorstraat 107,
# "Centre for Performing Arts"); it also tours nationally and abroad. The site
# is a Nuxt front-end on a cre8ion back-end whose JSON API the browser calls
# directly: POST `/prod/<lang>/api/events/programs` with
# `{"filters": {"startAt": ...}, "pagination": {"page", "pageSize" ≤ 100}}`
# returns one item per PERFORMANCE (`program`) with its date, theatre and city.
# Tickets are sold via Stager, which we never fetch (robots.txt); the price is
# whatever the event's free-text `oneLiner` states. See theater_utrecht_SOURCE.md.
BASE_URL = "https://www.theaterutrecht.nl"
API_URL = BASE_URL + "/prod/{lang}/api/events/programs"
VENUE_SLUG = "theater-utrecht"
PAGE_SIZE = 100
MAX_PAGES = 20

# Only performances in Theater Utrecht's own house. Its touring dates play in
# other cities, and its Utrecht dates at Stadsschouwburg Utrecht / Theater
# Kikker belong to those venues (and their own sources).
HOME_THEATER = "Theater Utrecht"
# Event "Type" attributes that aren't a public performance.
EXCLUDED_EVENT_TYPES = {"expositie"}
# Performance "Type" attributes: school-only performances aren't public.
EXCLUDED_PROGRAM_TYPES = {"schoolvoorstelling"}
# Shown as annotations; "In huis" just restates the venue.
_QUIET_TYPES = {"in huis", "voorstelling"}


def _attrs(obj: dict, type_name: str) -> list[str]:
    return [
        a.get("name") or ""
        for a in obj.get("attributes") or []
        if (a.get("type") or {}).get("name") == type_name
    ]


def _parse_dt(value: str | None) -> tuple[dt.date, dt.time | None] | None:
    if not value:
        return None
    try:
        stamp = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    t = stamp.time().replace(second=0, microsecond=0)
    return stamp.date(), (None if t == dt.time(0, 0) else t)


def keep(item: dict) -> bool:
    program = item.get("program") or {}
    if program.get("isCanceled"):
        return False
    if HOME_THEATER not in _attrs(program, "Theater"):
        return False
    if any(t.lower() in EXCLUDED_EVENT_TYPES for t in _attrs(item, "Type")):
        return False
    if any(t.lower() in EXCLUDED_PROGRAM_TYPES for t in _attrs(program, "Type")):
        return False
    return True


def _price(item: dict) -> str | None:
    program = item.get("program") or {}
    button = ((program.get("button") or {}).get("text") or "").lower()
    if "uitverkocht" in button or "sold out" in button:
        return "sold-out"
    text = item.get("oneLiner") or ""
    low = text.lower()
    found = c8.amounts(text)
    if found:
        # "€10 / €7,50", "Community €7.50 / General audience €12.50": the
        # lower tiers are reduced prices → the highest.
        return c8.highest(found)
    if "gratis" in low or "free entrance" in low or "vrije toegang" in low or "free" in button:
        return "free"
    return None


def _clean_html(value: str | None) -> str:
    return c8.clean(BeautifulSoup(value or "", "html.parser").get_text(" "))


def parse_programs(
    items: list[dict], english: list[dict] | None = None
) -> list[ScrapedEvent]:
    """API `events` items (nl, plus the en response for translations) → one
    ScrapedEvent per kept performance (pure)."""
    en_by_id = {
        (e.get("program") or {}).get("id"): e for e in (english or []) if e.get("program")
    }
    events: dict[str, ScrapedEvent] = {}
    for item in items:
        if not keep(item):
            continue
        program = item["program"]
        when = _parse_dt(program.get("startAt") or item.get("startAt"))
        title = c8.clean(item.get("title"))
        if not when or not title or not item.get("url"):
            continue
        start_date, start_time = when
        external_id = str(program["id"])
        types = [t for t in _attrs(program, "Type") if t.lower() not in _QUIET_TYPES]
        description = " — ".join(
            x for x in (
                c8.clean(item.get("subTitle")),
                c8.clean((item.get("fields") or {}).get("extraSubtitle")),
            ) if x
        ) or None
        translations = []
        en = en_by_id.get(program["id"])
        if en and en.get("url") and c8.clean(en.get("title")):
            translations.append(ScrapedTranslation(
                lang="en",
                title=c8.clean(en["title"]),
                source_url=urljoin(BASE_URL, en["url"]),
            ))
        image = (item.get("image1") or {}).get("url")
        events.setdefault(external_id, ScrapedEvent(
            title=title,
            start_date=start_date,
            start_time=start_time,
            source_url=urljoin(BASE_URL, item["url"]),
            category_slugs=["theater"],
            price=_price(item),
            description=description,
            image_url=image,
            external_id=external_id,
            annotations=types,
            translations=translations,
        ))
    return list(events.values())


def fetch_programs(http, lang: str, today: dt.date) -> list[dict]:
    items: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        r = http.post(
            API_URL.format(lang=lang),
            json={
                "filters": {"startAt": f"{today.isoformat()}T00:00:00"},
                "pagination": {"page": page, "pageSize": PAGE_SIZE},
                "sortings": [],
            },
        )
        r.raise_for_status()
        data = r.json()
        items.extend(data.get("events") or [])
        if page >= (data.get("pagination") or {}).get("pages", 1):
            break
    return items


class TheaterUtrechtScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        today = dt.date.today()
        with c8.client() as http:
            nl = fetch_programs(http, "nl", today)
            try:
                en = fetch_programs(http, "en", today)
            except Exception:  # translations are a nicety; never fail the run on them
                en = []
        return parse_programs(nl, en)


register(
    scraper=TheaterUtrechtScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Theater Utrecht",
        city_slug="utrecht",
        address="Boorstraat 107, 3513 SE Utrecht",
        site_url=BASE_URL + "/",
        instagram_url="https://www.instagram.com/theaterutrecht/",
        category_slugs=["theater"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
        ],
    ),
)
