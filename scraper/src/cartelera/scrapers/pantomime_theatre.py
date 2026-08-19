from __future__ import annotations
import datetime as dt

from cartelera.scrapers import register
from cartelera.scrapers.esora import EsoraFeedScraper
from cartelera.scrapers.esora import parse_feed as _esora_parse_feed
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# Yerevan State Pantomime Theatre. Own site (pantomime.am and variants) is
# dead — the theatre's channel is Instagram (@pantomime_theatre), ingested by
# esora.app's dedicated source page into the same feed shape as Malkhas/Kami.
# DORMANT as of 2026-08-19: the feed's `eventOccurrenceIds` is empty (0
# upcoming; ~10 lifetime events total) — the theatre appears to be between
# seasons. Registered anyway per the task brief: the nightly scraper run
# itself is the re-check, so events appear the moment esora repopulates
# (likely September, after the off-season). This is a thin wrapper over the
# shared esora-feed plumbing in esora.py. See pantomime_theatre_SOURCE.md.
VENUE_SLUG = "pantomime-theatre"
EVENT_SOURCE_ID = "17432552-b94e-41c7-8401-855e688d6a62"
CATEGORY_SLUGS = ["theater"]
# No blanket feed tag confirmed to exclude beyond the helper's default (the
# live feed is currently empty, so there's nothing to inspect); re-check once
# it repopulates.
EXCLUDED_TAGS: set[str] = set()


def parse_feed(json_text: str, today: dt.date | None = None) -> list[ScrapedEvent]:
    return _esora_parse_feed(
        json_text,
        category_slugs=CATEGORY_SLUGS,
        excluded_tags=EXCLUDED_TAGS,
        today=today,
    )


class PantomimeTheatreScraper(EsoraFeedScraper):
    def __init__(self) -> None:
        super().__init__(
            venue_slug=VENUE_SLUG,
            event_source_id=EVENT_SOURCE_ID,
            category_slugs=CATEGORY_SLUGS,
            excluded_tags=EXCLUDED_TAGS,
        )


register(
    scraper=PantomimeTheatreScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Yerevan State Pantomime Theatre",
        city_slug="yerevan",
        address="21 Gevorg Kochar St, Yerevan 0001, Armenia",
        site_url=None,  # the theatre's own site is dead
        instagram_url="https://www.instagram.com/pantomime_theatre",
        category_slugs=["theater"],
        list_memberships=[
            ListMembership(list_slug="theater"),
        ],
    ),
)
