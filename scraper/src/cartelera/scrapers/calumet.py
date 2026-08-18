from __future__ import annotations
import datetime as dt
import json
import re
from zoneinfo import ZoneInfo

import httpx

from cartelera.scrapers import register
from cartelera.types import (
    ListMembership,
    ScrapedEvent,
    ScrapedTranslation,
    VenueDefinition,
)

# Calumet Ethnic Lounge Bar, Yerevan — small live-music bar on Pushkin St.
# Like Malkhas (same street), Calumet has no scrapeable official site; its
# public programme lives on esora.app, which ingests the bar's Instagram
# posts into dated occurrences (artist/DJ, date, time, often a price line).
# Esora's own `category` field is the real discriminator: "clubbing" (DJ/B2B
# nights — Electro Almaza Tuesdays, Calcoolsun, B2B sets) vs "live_music" /
# "music" / "social" (live bands, acoustic sets, the bar's own parties). We
# checked every historical event (66 occurrences, Nov 2025-Aug 2026): zero
# mention "jazz" anywhere, so category_slugs is ["club", "folk"] — NOT
# ["folk", "jazz"] as initially hypothesized. See calumet_SOURCE.md.
VENUE_SLUG = "calumet"
EVENT_SOURCE_ID = "0d96db49-9628-4868-9c23-f283ebc86463"
FEED_URL = (
    "https://esora.app/api/events/feed"
    f"?eventSourceId={EVENT_SOURCE_ID}&limit=100&page={{page}}"
)
EVENT_PAGE_URL = "https://esora.app/{lang}/yerevan/events/{event_id}"
IMAGE_URL = (
    "https://esora.app/img/unsafe/1200x0/filters:no_upscale():format(jpeg)"
    "/events/{event_id}/{file_name}"
)
_MAX_PAGES = 10  # totalPages is 1 today; follow more defensively, never unbounded

_TZ = ZoneInfo("Asia/Yerevan")
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}

# esora's `category` field on the event (not a genre tag) is the real,
# stable discriminator between DJ/clubbing nights and everything else
# (live bands, acoustic sets, the venue's own social nights).
_CLUBBING = "clubbing"

# Placeholder tags esora fills in when it has no real genre signal
# ("live_music_other", "clubbing_other", ...) — not informative, dropped so
# annotations only carry real signal (e.g. "rock").
_PLACEHOLDER_TAG_RE = re.compile(r"_other$")

_FREE_RE = re.compile(r"no entrance fee|free entrance|^free$|entrance is free", re.I)
_RANGE_RE = re.compile(r"^([\d,]+)\s*[–-]\s*([\d,]+)\s*AMD$", re.I)
_RANGE_FACTOR = 2


def _i18n_text(entity: dict, field: str, lang: str) -> str | None:
    """Esora's per-locale display content: i18n.<field>.<lang>.content."""
    content = ((((entity.get("i18n") or {}).get(field)) or {}).get(lang) or {}).get(
        "content"
    )
    if isinstance(content, str) and content.strip():
        return content.strip()
    return None


def _price(raw) -> str | None:
    """Occurrence price is source free text (often unstated). Normalize the
    many "no cost" phrasings to "free"; collapse a minor AMD range (< 2x
    spread) to its higher value; pass any other text through as-is — never
    guess a number that isn't stated."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if _FREE_RE.search(text):
        return "free"
    match = _RANGE_RE.match(text)
    if match:
        lo = int(match.group(1).replace(",", ""))
        hi = int(match.group(2).replace(",", ""))
        if hi > 0 and hi >= _RANGE_FACTOR * lo:
            return f"{lo}–{hi} AMD"
        return f"{hi} AMD"
    return text


def _category_slugs(event: dict) -> list[str]:
    """clubbing -> club; live_music/music/social -> folk (the bar's live-band
    and in-house nights bucket). See module docstring: no event in the
    programme's history mentions jazz."""
    return ["club"] if event.get("category") == _CLUBBING else ["folk"]


def _annotations(event: dict) -> list[str]:
    return [t for t in event.get("tags") or [] if t and not _PLACEHOLDER_TAG_RE.search(t)]


def _image_url(event: dict, event_id: str) -> str | None:
    for media in event.get("media") or []:
        if media.get("type") == "image" and not media.get("isDisabled"):
            file_name = media.get("localFileName")
            if file_name:
                return IMAGE_URL.format(event_id=event_id, file_name=file_name)
    return None


def _translations(event: dict, event_id: str) -> list[ScrapedTranslation]:
    """ru/en content from the i18n block (hy is the canonical event)."""
    out: list[ScrapedTranslation] = []
    for lang in ("ru", "en"):
        title = _i18n_text(event, "title", lang)
        if not title:
            continue
        out.append(
            ScrapedTranslation(
                lang=lang,
                title=title,
                description=_i18n_text(event, "description", lang),
                source_url=EVENT_PAGE_URL.format(lang=lang, event_id=event_id),
            )
        )
    return out


def parse_feed(json_text: str, today: dt.date | None = None) -> list[ScrapedEvent]:
    """Parse one Esora events-feed API response into ScrapedEvents.

    One ScrapedEvent per non-disabled occurrence dated `today`-or-later
    (today defaults to the current date in Asia/Yerevan). Category comes
    from Esora's `category` field on the event, not a text guess: `clubbing`
    is a DJ/B2B night -> `club`; anything else (`live_music`, `music`,
    `social`) is a live band or in-house night -> `folk`.
    """
    if today is None:
        today = dt.datetime.now(_TZ).date()
    data = json.loads(json_text)
    occurrence_ids = (data.get("result") or {}).get("eventOccurrenceIds") or []
    entities = data.get("entities") or {}
    occurrences = entities.get("eventOccurrences") or {}
    events_by_id = entities.get("events") or {}

    events: list[ScrapedEvent] = []
    for occ_id in occurrence_ids:
        occ = occurrences.get(occ_id)
        if not occ or occ.get("disabledAt"):
            continue
        event = events_by_id.get(occ.get("eventId") or "")
        if not event or event.get("disabledAt"):
            continue
        event_id = event["eventId"]

        raw_date = occ.get("startDate")
        if not raw_date:
            continue
        try:
            start_date = dt.date.fromisoformat(raw_date)
        except ValueError:
            continue
        if start_date < today:
            continue

        start_time: dt.time | None = None
        raw_time = occ.get("startTime")
        if raw_time:
            try:
                start_time = dt.time.fromisoformat(raw_time)
            except ValueError:
                start_time = None

        title = _i18n_text(event, "title", "hy") or (event.get("title") or "").strip()
        if not title:
            continue
        description = _i18n_text(event, "description", "hy") or event.get("description")

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                start_times=[start_time] if start_time else [],
                end_date=dt.date.fromisoformat(occ["endDate"]) if occ.get("endDate") else None,
                source_url=EVENT_PAGE_URL.format(lang="hy", event_id=event_id),
                category_slugs=_category_slugs(event),
                price=_price(occ.get("price")),
                description=description,
                image_url=_image_url(event, event_id),
                external_id=f"esora-occ-{occ_id}",
                annotations=_annotations(event),
                translations=_translations(event, event_id),
            )
        )
    return events


class CalumetScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        with httpx.Client(follow_redirects=True, timeout=30, headers=_HEADERS) as client:
            page = 1
            while page <= _MAX_PAGES:
                response = client.get(FEED_URL.format(page=page))
                response.raise_for_status()
                events.extend(parse_feed(response.text))
                pagination = (response.json().get("result") or {}).get("pagination") or {}
                if page >= int(pagination.get("totalPages") or 1):
                    break
                page += 1
        return events


register(
    scraper=CalumetScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Calumet Ethnic Lounge Bar",
        city_slug="yerevan",
        address="56-a Pushkin St, 0002 Yerevan",
        site_url=None,  # no official website; esora.app is the only per-date listing
        instagram_url="https://www.instagram.com/calumetyerevan/",
        category_slugs=["club", "folk"],
        list_memberships=[
            ListMembership(list_slug="club", whitelist_category_slug="club"),
            ListMembership(list_slug="folk", whitelist_category_slug="folk"),
        ],
    ),
)
