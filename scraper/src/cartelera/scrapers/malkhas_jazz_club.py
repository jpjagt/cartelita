from __future__ import annotations
import datetime as dt

from cartelera.scrapers import register
from cartelera.scrapers.esora import EsoraFeedScraper
from cartelera.scrapers.esora import parse_feed as _esora_parse_feed
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# Malkhas Jazz Club, Yerevan — live jazz seven nights a week from 21:00. The
# club has NO official website (malkhas.am is dead; its channels are
# Instagram/Facebook), so the source is esora.app's dedicated Malkhas page,
# which ingests the club's weekly Instagram line-up into one dated occurrence
# per night. This is a thin wrapper over the shared esora-feed plumbing in
# esora.py (feed URL/pagination, entity parsing, slot-dedup) — it only fixes
# the venue's `eventSourceId`, its single category (`jazz` — the club
# programs only live jazz; the feed agrees: category=live_music,
# tags=["jazz"]), and excludes the `jazz` tag from annotations (it's the
# category discriminator, not an additional label). See
# malkhas_jazz_club_SOURCE.md.
VENUE_SLUG = "malkhas-jazz-club"
EVENT_SOURCE_ID = "2f85265c-78f0-4a7c-9580-43163182c3cf"
CATEGORY_SLUGS = ["jazz"]
EXCLUDED_TAGS = {"jazz"}


def parse_feed(json_text: str, today: dt.date | None = None) -> list[ScrapedEvent]:
    return _esora_parse_feed(
        json_text,
        category_slugs=CATEGORY_SLUGS,
        excluded_tags=EXCLUDED_TAGS,
        today=today,
    )


class MalkhasJazzClubScraper(EsoraFeedScraper):
    def __init__(self) -> None:
        super().__init__(
            venue_slug=VENUE_SLUG,
            event_source_id=EVENT_SOURCE_ID,
            category_slugs=CATEGORY_SLUGS,
            excluded_tags=EXCLUDED_TAGS,
        )


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
