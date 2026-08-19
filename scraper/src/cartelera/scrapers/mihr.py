from __future__ import annotations
import datetime as dt

from cartelera.scrapers import register
from cartelera.scrapers.esora import EsoraFeedScraper
from cartelera.scrapers.esora import parse_feed as _esora_parse_feed
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# Mihr Theatre, Yerevan — a contemporary dance company (not a fixed venue: it
# tours/performs at different halls), with its own site at mihrtheatre.com.
# esora.app runs a dedicated source page ingesting the company's Instagram
# (@mihrtheatre) posts, same feed shape as Malkhas/Kami/Pantomime. DORMANT as
# of 2026-08-19: the feed's `eventOccurrenceIds` is empty. Registered anyway
# per the task brief: the nightly scraper run itself is the re-check, so
# events appear the moment esora repopulates. This is a thin wrapper over the
# shared esora-feed plumbing in esora.py. See mihr_SOURCE.md.
VENUE_SLUG = "mihr"
EVENT_SOURCE_ID = "82d1073c-6107-4dfd-b14e-533c0bcd29c9"
CATEGORY_SLUGS = ["dance"]
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


class MihrScraper(EsoraFeedScraper):
    def __init__(self) -> None:
        super().__init__(
            venue_slug=VENUE_SLUG,
            event_source_id=EVENT_SOURCE_ID,
            category_slugs=CATEGORY_SLUGS,
            excluded_tags=EXCLUDED_TAGS,
        )


register(
    scraper=MihrScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Mihr Theatre",
        city_slug="yerevan",
        address=None,  # touring contemporary-dance company, no fixed venue
        site_url="https://mihrtheatre.com",
        instagram_url="https://www.instagram.com/mihrtheatre",
        category_slugs=["dance"],
        list_memberships=[
            ListMembership(list_slug="dance"),
        ],
    ),
)
