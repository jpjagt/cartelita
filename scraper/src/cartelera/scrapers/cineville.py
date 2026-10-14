from __future__ import annotations
import datetime as dt
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from cartelera.scrapers import register_source
from cartelera.scrapers.http import CARTELITA_UA
from cartelera.types import (
    ListMembership,
    ScrapedEvent,
    SourceDefinition,
    VenueDefinition,
)

# Cineville (cineville.nl) — the Dutch arthouse-cinema subscription network.
# Its public, unauthenticated JSON API carries every member cinema's screenings
# (one event per occurrence) with an embedded "production" (the film). This is
# a MULTI-VENUE WHITELIST source: only the Rotterdam/Utrecht cinemas this
# source owns per docs/nl-cities-plan.md are fetched. Cineville also lists
# Amsterdam cinemas (film there comes from jazzin), LantarenVenster and WORM
# (own scrapers) — deliberately NOT included. See cineville_SOURCE.md.
API_BASE = "https://api.cineville.nl"
FILM_PAGE = "https://www.cineville.nl/films/{slug}"
SOURCE_SLUG = "cineville"
USER_AGENT = CARTELITA_UA
TZ = ZoneInfo("Europe/Amsterdam")
PAGE_LIMIT = 200

# venue_slug -> Cineville venue UUID (from GET /venues).
VENUE_IDS: dict[str, str] = {
    "kino-rotterdam": "57922ba0-1dba-49bc-b893-2be7b8d9ef4d",
    "cinerama": "90c6c215-c9b0-4461-987e-edbc096e219a",
    "wenneker": "8e7736a9-ee16-4f52-9abf-fa1a897af697",
    "louis-hartlooper": "fd5a6386-c176-4839-8641-07fac03ca2e2",
    "springhaver": "c15751d4-4d4b-4cc8-a158-70f2c8fe4cb7",
    "slachtstraat": "ddb268bf-0634-4f5d-b396-e7a5549d2451",
    "de-sien": "310f9378-52b5-4aaf-b7b6-4b4b1f6fb1bb",
}
VENUE_BY_ID: dict[str, str] = {uuid: slug for slug, uuid in VENUE_IDS.items()}

# Curation: non-programme series a venue sells through its POS (and hence
# Cineville) without marking them hidden. Cineville's API has no structural
# field for these, so each entry is an exact, named series that the VENUE'S
# OWN SITE classifies as a course/workshop (checked 2026-10-14) — not a title
# keyword guess. Matched against the venue's POS title (productionHint).
# Keep in sync with "Exclusions" in cineville_SOURCE.md.
EXCLUDED_SERIES: dict[str, list[re.Pattern[str]]] = {
    "louis-hartlooper": [
        # hartlooper.nl "Genre: Filmcursus" — multi-week lecture courses.
        re.compile(r"^De Ins en Outs van Film\b", re.IGNORECASE),
        re.compile(r"^Het Verhaal van de Documentairemaker$", re.IGNORECASE),
        re.compile(r"^Van Klassieker tot Pulp$", re.IGNORECASE),
        re.compile(r"^Film als Filosofie$", re.IGNORECASE),
    ],
    "slachtstraat": [
        # slachtstraat.nl: "een unieke schrijfworkshop".
        re.compile(r"^(Het )?Schrijfcaf[ée]$", re.IGNORECASE),
    ],
    "de-sien": [
        # Cinekid's day-long interactive media workshop, not a screening.
        re.compile(r"^Cinekid Medialab$", re.IGNORECASE),
    ],
    "kino-rotterdam": [
        # A bare POS placeholder titled "Event" whose ticket page is empty —
        # a booking, not a public screening.
        re.compile(r"^Event$", re.IGNORECASE),
    ],
}


def is_excluded(venue_slug: str, pos_title: str | None) -> bool:
    if not pos_title:
        return False
    return any(p.search(pos_title) for p in EXCLUDED_SERIES.get(venue_slug, []))


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    return text or None


def _parse_utc(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(TZ)


def _language(subtitles: list[str] | None) -> str | None:
    """Cineville's `attributes.subtitles` is a list of ISO codes for the
    subtitle track ("nl", "en"). Shown as stated ("EN subs"); never inferred
    from the film's spoken language. Empty/missing -> None."""
    codes = [c.strip().upper() for c in (subtitles or []) if c and c.strip()]
    return f"{'/'.join(codes)} subs" if codes else None


# De Sien states English subtitles in its POS title ("Youri | Eng Subs")
# instead of Cineville's subtitles field; lift that suffix into `language`.
_TITLE_SUBS = re.compile(r"\s*\|\s*(?:Eng|English|EN)\s+Subs?\s*$", re.IGNORECASE)


def _source_url(event: dict, production: dict | None) -> str:
    """The per-occurrence ticket link on the venue's own site. Some venues
    (Cinerama) give only their homepage — then the Cineville film page, which
    lists every screening, is the more useful link."""
    ticket = event.get("ticketingUrl") or ""
    if ticket and urlsplit(ticket).path.strip("/"):
        return ticket
    if production and production.get("slug"):
        return FILM_PAGE.format(slug=production["slug"])
    return ticket or "https://www.cineville.nl/"


def parse_events(items: list[dict]) -> list[ScrapedEvent]:
    """Raw Cineville API event objects (with `embed[production]=true`) ->
    one ScrapedEvent per occurrence. Pure: no network.

    Drops hidden events (`isHidden`: rentals "Verhuur", school screenings,
    staff sessions the venue keeps off its public listing), the named
    non-programme series in EXCLUDED_SERIES, and events at venues outside the
    whitelist.
    """
    events: list[ScrapedEvent] = []
    for item in items:
        venue_slug = VENUE_BY_ID.get(item.get("venueId", ""))
        if venue_slug is None or item.get("isHidden"):
            continue
        production = (item.get("_embedded") or {}).get("production")
        hint = item.get("productionHint") or {}
        # The venue's own (POS) title for this screening carries occurrence
        # detail ("Vertigo (1958) a 70mm presentation", "Purple Rain (1984)
        # singalong") that the shared production title drops; fall back to the
        # production title for the rare event without one.
        title = _clean(hint.get("title")) or _clean((production or {}).get("title"))
        if is_excluded(venue_slug, _clean(hint.get("title"))):
            continue
        if not title or not item.get("startDate"):
            continue
        attrs = item.get("attributes") or {}
        language = _language(attrs.get("subtitles"))
        if _TITLE_SUBS.search(title):
            title = _TITLE_SUBS.sub("", title)
            language = language or "EN subs"
        start = _parse_utc(item["startDate"])
        end = _parse_utc(item["endDate"]) if item.get("endDate") else None

        description = image_url = None
        if production:
            loc = production.get("localizableAttributes") or {}
            description = _clean(loc.get("shortDescription"))
            assets = production.get("assets") or {}
            for key in ("cover", "poster"):
                if (assets.get(key) or {}).get("url"):
                    image_url = assets[key]["url"]
                    break

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start.date(),
                start_time=start.time().replace(second=0, microsecond=0),
                end_date=end.date() if end else None,
                end_time=end.time().replace(second=0, microsecond=0) if end else None,
                source_url=_source_url(item, production),
                category_slugs=["film"],
                price=None,  # Cineville carries no price (pass-holders watch free)
                language=language,
                description=description,
                image_url=image_url,
                annotations=[t for t in (attrs.get("tags") or []) if t],
                # Cineville's event id is one screening (verified stable across
                # fetches) — already per-occurrence.
                external_id=item["id"],
                venue_slug=venue_slug,
            )
        )
    return events


def _fetch_venue(client: httpx.Client, venue_uuid: str, since: dt.datetime) -> list[dict]:
    params = (
        f"venueId[eq]={venue_uuid}"
        f"&startDate[gte]={since.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f"&embed[production]=true&page[limit]={PAGE_LIMIT}"
    )
    url: str | None = f"{API_BASE}/events?{params}"
    items: list[dict] = []
    for _ in range(50):  # cursor pagination; guard against a looping cursor
        if url is None:
            break
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        items.extend((data.get("_embedded") or {}).get("events") or [])
        nxt = ((data.get("_links") or {}).get("next") or {}).get("href")
        url = f"{API_BASE}{nxt}" if nxt else None
    return items


class CinevilleScraper:
    def scrape(self) -> list[ScrapedEvent]:
        today = dt.datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        items: list[dict] = []
        with httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=30,
            follow_redirects=True,
        ) as client:
            for venue_uuid in VENUE_IDS.values():
                items.extend(_fetch_venue(client, venue_uuid, today))
        return parse_events(items)


_FILM = [ListMembership(list_slug="film", whitelist_category_slug="film")]


def _venue(slug: str, name: str, city: str, address: str, site: str) -> VenueDefinition:
    return VenueDefinition(
        slug=slug, name=name, city_slug=city, address=address, site_url=site,
        category_slugs=["film"], list_memberships=list(_FILM),
    )


VENUES = [
    _venue("kino-rotterdam", "KINO", "rotterdam",
           "Gouvernestraat 129-133, 3014 PM Rotterdam", "https://kinorotterdam.nl"),
    _venue("cinerama", "Cinerama", "rotterdam",
           "Westblaak 18, 3012 KL Rotterdam", "https://cineramabios.nl"),
    _venue("wenneker", "Wenneker Cinema", "rotterdam",
           "Vijgensteeg 2, 3111 PT Schiedam", "https://www.wennekercinema.nl"),
    _venue("louis-hartlooper", "Louis Hartlooper Complex", "utrecht",
           "Tolsteegbrug 1, 3511 ZN Utrecht", "https://www.hartlooper.nl"),
    _venue("springhaver", "Springhaver", "utrecht",
           "Springweg 50, 3511 VS Utrecht", "https://www.springhaver.nl"),
    _venue("slachtstraat", "Slachtstraat Filmtheater", "utrecht",
           "Slachtstraat 5, 3512 BC Utrecht", "https://www.slachtstraat.nl"),
    _venue("de-sien", "De Sien", "utrecht",
           "Kanaalweg 30, 3526 KM Utrecht", "https://desienfilm.nl"),
]

register_source(
    scraper=CinevilleScraper(),
    source=SourceDefinition(slug=SOURCE_SLUG, name="Cineville", venues=VENUES),
)
