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

# Malkhas Jazz Club, Yerevan — live jazz seven nights a week from 21:00. The
# club has NO official website (malkhas.am is dead; its channels are
# Instagram/Facebook), so the source is esora.app's dedicated Malkhas page,
# which ingests the club's weekly Instagram line-up into one dated occurrence
# per night. We call the same public JSON API the page itself calls; it returns
# normalized entities: events (artist, en/hy/ru i18n content, media, tags) and
# eventOccurrences (ISO date, 21:00 start, price — always null: no published
# cover charge). Canonical content is hy (Yerevan's default locale); ru+en ship
# as translations. See malkhas_jazz_club_SOURCE.md.
VENUE_SLUG = "malkhas-jazz-club"
EVENT_SOURCE_ID = "2f85265c-78f0-4a7c-9580-43163182c3cf"
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
    """Occurrence price is null today; render a numeric value in AMD, pass a
    string through — never guess."""
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
    `jazz` — the venue programs only live jazz (the feed agrees:
    category=live_music, tags=["jazz"]); non-jazz feed tags go to annotations.
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

        tags = [t for t in event.get("tags") or [] if t and t != "jazz"]

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                start_times=[start_time] if start_time else [],
                end_date=dt.date.fromisoformat(occ["endDate"]) if occ.get("endDate") else None,
                source_url=EVENT_PAGE_URL.format(lang="hy", event_id=event_id),
                category_slugs=["jazz"],
                price=_price(occ.get("price")),
                description=description,
                image_url=_image_url(event, event_id),
                external_id=f"esora-occ-{occ_id}",
                annotations=tags,
                translations=_translations(event, event_id),
            )
        )
    return events


class MalkhasJazzClubScraper:
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
    scraper=MalkhasJazzClubScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Malkhas Jazz Club",
        city_slug="yerevan",
        address="52/1 Pushkin St, 0002 Yerevan",
        site_url=None,  # malkhas.am is dead; the club has no official website
        instagram_url="https://www.instagram.com/malkhasclub/",
        category_slugs=["jazz"],
        list_memberships=[
            ListMembership(list_slug="jazz"),
        ],
    ),
)
