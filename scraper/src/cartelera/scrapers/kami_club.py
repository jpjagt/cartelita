from __future__ import annotations
import datetime as dt
import json
from zoneinfo import ZoneInfo

import httpx

from cartelera.scrapers import register
from cartelera.types import (
    ListMembership,
    ScrapedEvent,
    ScrapedTranslation,
    VenueDefinition,
)

# Kami Music Club, Yerevan — live-music club at 18 Abovyan St. (behind the
# Moscow Opera House); live bands "of various genres" most nights from
# ~21:00, resident band Kami Friends, ~5000-7000 AMD door. The club has NO
# official website (only Instagram/Facebook + third-party directory
# listings), so the source is esora.app's dedicated Kami source page, fed
# from the club's weekly Instagram line-up posts, exactly like the Malkhas
# Jazz Club scraper. Esora's feed never discriminates genre beyond a single
# blanket tag (`live_music_other` on every event — no jazz/rock/blues split),
# so per the task brief we file the whole programme under the single `rock`
# category; the tag itself is the discriminator-that-isn't and is excluded
# from annotations (nothing else is present to carry there). See
# kami_club_SOURCE.md.
VENUE_SLUG = "kami-club"
EVENT_SOURCE_ID = "a1fbbfa7-8119-4fd6-a348-9f8df287ae45"
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


def _i18n_text(entity: dict, field: str, lang: str) -> str | None:
    """Esora's per-locale display content: i18n.<field>.<lang>.content."""
    content = ((((entity.get("i18n") or {}).get(field)) or {}).get(lang) or {}).get(
        "content"
    )
    if isinstance(content, str) and content.strip():
        return content.strip()
    return None


def _price(raw) -> str | None:
    """Occurrence price is a free-text string ("5000 AMD") or null; pass the
    string through as-is (already in-convention), render a bare number
    defensively, never guess when null."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return f"{int(raw)} AMD" if raw else "free"
    text = str(raw).strip()
    return text or None


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
    (today defaults to the current date in Asia/Yerevan). Category is always
    `rock` — the feed carries no genre discriminator (every event/occurrence
    is tagged `live_music_other`), so the whole programme is filed under the
    single category per the task brief.

    Esora occasionally double-ingests the same night as two distinct
    `eventId`s (duplicate Instagram-post ingestion) that land on the exact
    same `startDate`+`startTime` — a physical impossibility for a single
    venue, unlike two genuinely different clock times the same night (an
    early/late show, which IS kept as two occurrences). Those exact
    date+time duplicates are collapsed to one occurrence, preferring
    whichever copy has a price.
    """
    if today is None:
        today = dt.datetime.now(_TZ).date()
    data = json.loads(json_text)
    occurrence_ids = (data.get("result") or {}).get("eventOccurrenceIds") or []
    entities = data.get("entities") or {}
    occurrences = entities.get("eventOccurrences") or {}
    events_by_id = entities.get("events") or {}

    # First pass: collect valid, non-disabled, future-or-today occurrences,
    # collapsing exact date+time duplicates (keep the priced copy if any).
    kept_by_slot: dict[tuple[dt.date, dt.time | None], str] = {}
    ordered_slots: list[tuple[dt.date, dt.time | None]] = []
    parsed_occ: dict[str, tuple[dt.date, dt.time | None]] = {}

    for occ_id in occurrence_ids:
        occ = occurrences.get(occ_id)
        if not occ or occ.get("disabledAt"):
            continue
        event = events_by_id.get(occ.get("eventId") or "")
        if not event or event.get("disabledAt"):
            continue

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

        slot = (start_date, start_time)
        parsed_occ[occ_id] = slot
        if slot not in kept_by_slot:
            kept_by_slot[slot] = occ_id
            ordered_slots.append(slot)
        else:
            current = occurrences[kept_by_slot[slot]]
            if current.get("price") is None and occ.get("price") is not None:
                kept_by_slot[slot] = occ_id

    events: list[ScrapedEvent] = []
    for slot in ordered_slots:
        occ_id = kept_by_slot[slot]
        occ = occurrences[occ_id]
        event = events_by_id[occ["eventId"]]
        event_id = event["eventId"]
        start_date, start_time = slot

        title = _i18n_text(event, "title", "hy") or (event.get("title") or "").strip()
        if not title:
            continue
        description = _i18n_text(event, "description", "hy") or event.get("description")

        tags = [t for t in event.get("tags") or [] if t and t != "live_music_other"]

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                start_times=[start_time] if start_time else [],
                end_date=dt.date.fromisoformat(occ["endDate"]) if occ.get("endDate") else None,
                source_url=EVENT_PAGE_URL.format(lang="hy", event_id=event_id),
                category_slugs=["rock"],
                price=_price(occ.get("price")),
                description=description,
                image_url=_image_url(event, event_id),
                external_id=f"esora-occ-{occ_id}",
                annotations=tags,
                translations=_translations(event, event_id),
            )
        )
    return events


class KamiClubScraper:
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
    scraper=KamiClubScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Kami Music Club",
        city_slug="yerevan",
        address="18 Abovyan St, Yerevan",
        site_url=None,  # no official website; only Instagram/Facebook + directory listings
        instagram_url="https://www.instagram.com/kami.musicclub/",
        category_slugs=["rock"],
        list_memberships=[
            ListMembership(list_slug="rock"),
        ],
    ),
)
