from __future__ import annotations
import datetime as dt
import json
from collections.abc import Iterable
from zoneinfo import ZoneInfo

import httpx

from cartelera.scrapers.price import normalize_amd
from cartelera.types import ScrapedEvent, ScrapedTranslation

# Shared plumbing for every esora.app-fed Yerevan venue scraper (Malkhas Jazz
# Club, Kami Music Club, Pantomime Theatre, Mihr Theatre, ...). Each venue has
# a dedicated esora.app "source" page fed from its own weekly Instagram
# line-up posts; esora.app exposes the same page state as a public JSON feed
# API, one dated occurrence per post. All four consumers share this exact
# plumbing — the feed URL/pagination scheme, the entity shapes, and kami's
# exact-(startDate, startTime) slot-dedup (two identical date+times at one
# venue is a double-ingest of the same Instagram post; different clock times
# are a genuine early/late show and both survive — see
# kami_club_SOURCE.md's "Quirk" section for the discovery story). What
# differs per venue is parametrized: which `eventSourceId` to fetch, which
# category slug(s) an occurrence gets filed under, and which feed tags are
# excluded from `annotations` (a venue's blanket genre/type tag duplicates
# the category and shouldn't leak in).
FEED_URL = (
    "https://esora.app/api/events/feed"
    "?eventSourceId={event_source_id}&limit=100&page={page}"
)
EVENT_PAGE_URL = "https://esora.app/{lang}/yerevan/events/{event_id}"
IMAGE_URL = (
    "https://esora.app/img/unsafe/1200x0/filters:no_upscale():format(jpeg)"
    "/events/{event_id}/{file_name}"
)
_MAX_PAGES = 10  # totalPages is 1 for every known esora feed; follow more defensively, never unbounded

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
        return f"{int(raw)}֏" if raw else "free"
    text = normalize_amd(str(raw).strip())
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


def parse_feed(
    json_text: str,
    category_slugs: list[str],
    excluded_tags: Iterable[str] = (),
    today: dt.date | None = None,
) -> list[ScrapedEvent]:
    """Parse one Esora events-feed API response into ScrapedEvents.

    One ScrapedEvent per non-disabled occurrence dated `today`-or-later
    (today defaults to the current date in Asia/Yerevan). `category_slugs` is
    filed on every occurrence unchanged (each esora-fed venue programs a
    single, fixed category — the feed itself carries no per-event genre
    discriminator worth splitting on). `excluded_tags` strips a venue's
    blanket genre/type feed tag out of `annotations` so the category
    discriminator never leaks back in as an annotation.

    Esora occasionally double-ingests the same night as two distinct
    `eventId`s (duplicate Instagram-post ingestion) that land on the exact
    same `startDate`+`startTime` — a physical impossibility for a single
    venue, unlike two genuinely different clock times the same night (an
    early/late show, which IS kept as two occurrences). Those exact
    date+time duplicates are collapsed to one occurrence, preferring
    whichever copy has a price. This dedup applies to every esora-fed venue,
    not just the one (Kami) where it was first observed — a harmless no-op
    for feeds without the wrinkle.
    """
    if today is None:
        today = dt.datetime.now(_TZ).date()
    excluded = set(excluded_tags)
    data = json.loads(json_text)
    occurrence_ids = (data.get("result") or {}).get("eventOccurrenceIds") or []
    entities = data.get("entities") or {}
    occurrences = entities.get("eventOccurrences") or {}
    events_by_id = entities.get("events") or {}

    # First pass: collect valid, non-disabled, future-or-today occurrences,
    # collapsing exact date+time duplicates (keep the priced copy if any).
    kept_by_slot: dict[tuple[dt.date, dt.time | None], str] = {}
    ordered_slots: list[tuple[dt.date, dt.time | None]] = []

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

        tags = [t for t in event.get("tags") or [] if t and t not in excluded]

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                start_times=[start_time] if start_time else [],
                end_date=dt.date.fromisoformat(occ["endDate"]) if occ.get("endDate") else None,
                source_url=EVENT_PAGE_URL.format(lang="hy", event_id=event_id),
                category_slugs=list(category_slugs),
                price=_price(occ.get("price")),
                description=description,
                image_url=_image_url(event, event_id),
                external_id=f"esora-occ-{occ_id}",
                annotations=tags,
                translations=_translations(event, event_id),
            )
        )
    return events


class EsoraFeedScraper:
    """Generic esora-feed scraper for one venue: the paginated httpx fetch
    loop + parse_feed, parametrized by the venue's `eventSourceId`, category
    slug(s), and excluded tags. Concrete venue modules instantiate this (see
    malkhas_jazz_club.py for the thin-wrapper pattern) and register() it."""

    def __init__(
        self,
        venue_slug: str,
        event_source_id: str,
        category_slugs: list[str],
        excluded_tags: Iterable[str] = (),
    ) -> None:
        self.venue_slug = venue_slug
        self.event_source_id = event_source_id
        self.category_slugs = category_slugs
        self.excluded_tags = excluded_tags

    def scrape(self) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        with httpx.Client(follow_redirects=True, timeout=30, headers=_HEADERS) as client:
            page = 1
            while page <= _MAX_PAGES:
                url = FEED_URL.format(event_source_id=self.event_source_id, page=page)
                response = client.get(url)
                response.raise_for_status()
                events.extend(
                    parse_feed(response.text, self.category_slugs, self.excluded_tags)
                )
                pagination = (response.json().get("result") or {}).get("pagination") or {}
                if page >= int(pagination.get("totalPages") or 1):
                    break
                page += 1
        return events
