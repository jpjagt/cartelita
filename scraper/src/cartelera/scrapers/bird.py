from __future__ import annotations

import datetime as dt
import json
import re
import urllib.parse
from zoneinfo import ZoneInfo

from cartelera.scrapers import register
from cartelera.scrapers._nl_common import first_time
from cartelera.scrapers.http import CARTELITA_COMPAT_UA, fetch
from cartelera.scrapers.price import eur_price
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# BIRD (Raampoortstraat, Rotterdam) — jazz/soul/hip-hop concert stage + club.
# The Next.js site is fed by a PUBLIC Prismic CMS repository; we read its
# documents API directly: one `agenda` document per occurrence with
# `event_date` (UTC), `times` (free text "Start 20:30 | Doors 19:30" /
# "23:00 - 04:00"), `price` (free text), `ticket_state`, `genres` and
# `main_categories` (club / live / mavis / food / garden). See bird_SOURCE.md.
#
# Category = BIRD's own `main_category`: club → club; live → jazz when BIRD
# tags it with its "jazz" genre, else pop (soul/hip-hop/folk concerts). The
# "mavis" category (the free weekly bar session in BIRD's restaurant Mavis)
# and food/garden-only items are not programme and are left out. BIRD also
# lists the shows it co-presents at OTHER venues (LantarenVenster, De Doelen,
# Annabel, Maassilo, V11) — dropped: those venues own their own listings.
API_ROOT = "https://bird-rotterdam.cdn.prismic.io/api/v2"
SITE_URL = "https://www.bird-rotterdam.nl"
VENUE_SLUG = "bird"
TZ = ZoneInfo("Europe/Amsterdam")
PAGE_SIZE = 100
MAX_PAGES = 10

PROGRAMME_CATEGORIES = {"club", "live"}

# An event BIRD presents elsewhere: a top title / subtitle "At LantarenVenster",
# "AT MAASSILO", or the description's "Let op: dit concert vindt plaats bij
# Annabel …, en niet bij BIRD" / "vindt plaats bij LantarenVenster, niet BIRD".
_ELSEWHERE_LABEL = re.compile(r"^\s*at\s+\S", re.IGNORECASE)
_ELSEWHERE_TEXT = re.compile(r"niet\s+(?:bij\s+)?BIRD|not\s+at\s+BIRD", re.IGNORECASE)
_ELSEWHERE_UID = re.compile(r"-at-(?!bird)[a-z]")
_START = re.compile(r"(?:start|aanvang|concert)\s*:?\s*(\d{1,2}[:.]\d{2})", re.IGNORECASE)
_SOLD_OUT = re.compile(r"sold\s*-?\s*out|uitverkocht", re.IGNORECASE)
_FREE = re.compile(r"^\s*(gratis|free)\b", re.IGNORECASE)


def _rich_text(value) -> str:
    """Plain text of a Prismic rich-text field (a list of blocks)."""
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return ""
    return "\n".join(b.get("text", "") for b in value if isinstance(b, dict))


def _slice_text(data: dict) -> str:
    parts: list[str] = []
    for s in data.get("slices") or []:
        for v in (s.get("primary") or {}).values():
            parts.append(_rich_text(v))
    return "\n".join(p for p in parts if p)


def _main_categories(data: dict) -> list[str]:
    out: list[str] = []
    for m in data.get("main_categories") or []:
        uid = (m.get("main_category") or {}).get("uid")
        if uid:
            out.append(uid)
    return out


def _genres(data: dict) -> list[tuple[str, str]]:
    """(uid, display title) per tagged genre; broken links are skipped."""
    out: list[tuple[str, str]] = []
    for g in data.get("genres") or []:
        link = g.get("genre") or {}
        uid = link.get("uid")
        if not uid:
            continue
        title = _rich_text((link.get("data") or {}).get("title")).strip() or uid
        out.append((uid, title))
    return out


def is_elsewhere(doc: dict) -> bool:
    """True when BIRD lists this show but it takes place at another venue."""
    data = doc.get("data") or {}
    for key in ("top_title", "subtitle"):
        if _ELSEWHERE_LABEL.match(data.get(key) or ""):
            return True
    if _ELSEWHERE_UID.search(doc.get("uid") or ""):
        return True
    return bool(_ELSEWHERE_TEXT.search(_slice_text(data)))


def _category(main: list[str], genre_uids: list[str]) -> str | None:
    if "club" in main:
        return "club"
    if "live" in main:
        return "jazz" if "jazz" in genre_uids else "pop"
    return None


def _start_time(times: str, local: dt.datetime) -> dt.time | None:
    m = _START.search(times)
    if m:
        return first_time(m.group(1))
    t = first_time(times)
    if t:
        return t
    return local.time() if (local.hour, local.minute) != (0, 0) else None


def _price(data: dict) -> str | None:
    price = (data.get("price") or "").strip()
    state = (data.get("ticket_state") or "").strip()
    if _SOLD_OUT.search(price) or _SOLD_OUT.search(state):
        return "sold-out"
    if _FREE.match(price) or state.lower() == "gratis":
        return "free"
    return eur_price(price)


def parse_documents(docs: list[dict]) -> list[ScrapedEvent]:
    """Prismic `agenda` documents → ScrapedEvents (pure; no network)."""
    events: list[ScrapedEvent] = []
    for doc in docs:
        if doc.get("type") != "agenda":
            continue
        data = doc.get("data") or {}
        main = _main_categories(data)
        if not PROGRAMME_CATEGORIES & set(main):
            continue  # mavis bar sessions, food, garden
        if is_elsewhere(doc):
            continue
        genres = _genres(data)
        category = _category(main, [u for u, _ in genres])
        if category is None:
            continue
        title = _rich_text(data.get("title")).strip()
        raw_date = data.get("event_date")
        if not title or not raw_date:
            continue
        local = dt.datetime.fromisoformat(raw_date.replace("+0000", "+00:00")).astimezone(TZ)
        times = _rich_text(data.get("times"))

        annotations: list[str] = []
        top = (data.get("top_title") or "").strip()
        if top:
            annotations.append(top)
        for _, name in genres:
            if name not in annotations:
                annotations.append(name)

        image = (data.get("cover_image") or {}).get("url")
        uid = doc.get("uid") or doc["id"]
        events.append(
            ScrapedEvent(
                title=title,
                start_date=local.date(),
                start_time=_start_time(times, local),
                source_url=f"{SITE_URL}/event/{uid}/",
                category_slugs=[category],
                price=_price(data),
                description=(data.get("meta_description") or None),
                image_url=image,
                external_id=doc["id"],
                annotations=annotations,
            )
        )
    return events


def _query_url(ref: str, today: dt.date, page: int) -> str:
    since = (today - dt.timedelta(days=1)).isoformat()
    q = f'[[at(document.type,"agenda")][date.after(my.agenda.event_date,"{since}")]]'
    params = {
        "ref": ref,
        "q": q,
        "lang": "nl-nl",
        "pageSize": str(PAGE_SIZE),
        "page": str(page),
        "orderings": "[my.agenda.event_date]",
        "fetchLinks": "genres.title,main_category.title",
    }
    return f"{API_ROOT}/documents/search?{urllib.parse.urlencode(params)}"


class BirdScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        headers = {"User-Agent": CARTELITA_COMPAT_UA}
        root = json.loads(fetch(API_ROOT, headers=headers))
        ref = next(r["ref"] for r in root["refs"] if r.get("isMasterRef"))
        today = dt.datetime.now(TZ).date()
        docs: list[dict] = []
        for page in range(1, MAX_PAGES + 1):
            body = json.loads(fetch(_query_url(ref, today, page), headers=headers))
            docs.extend(body.get("results") or [])
            if page >= (body.get("total_pages") or 1):
                break
        return parse_documents(docs)


register(
    scraper=BirdScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="BIRD",
        city_slug="rotterdam",
        address="Raampoortstraat 24-28, 3032 AH Rotterdam",
        site_url=SITE_URL + "/",
        instagram_url="https://www.instagram.com/birdrotterdam",
        category_slugs=["jazz", "pop", "club"],
        list_memberships=[
            ListMembership(list_slug="jazz", whitelist_category_slug="jazz"),
            ListMembership(list_slug="pop", whitelist_category_slug="pop"),
            ListMembership(list_slug="club", whitelist_category_slug="club"),
        ],
    ),
)
