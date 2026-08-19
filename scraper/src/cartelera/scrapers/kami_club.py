from __future__ import annotations
import datetime as dt

from cartelera.scrapers import register
from cartelera.scrapers.esora import EsoraFeedScraper
from cartelera.scrapers.esora import parse_feed as _esora_parse_feed
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# Kami Music Club, Yerevan — live-music club at 18 Abovyan St. (behind the
# Moscow Opera House); live bands "of various genres" most nights from
# ~21:00, resident band Kami Friends, ~5000-7000 AMD door. The club has NO
# official website (only Instagram/Facebook + third-party directory
# listings), so the source is esora.app's dedicated Kami source page, fed
# from the club's weekly Instagram line-up posts, exactly like the Malkhas
# Jazz Club scraper. This is a thin wrapper over the shared esora-feed
# plumbing in esora.py (feed URL/pagination, entity parsing, slot-dedup) — it
# only fixes the venue's `eventSourceId`, its single category. Esora's feed
# never discriminates genre beyond a single blanket tag (`live_music_other`
# on every event — no jazz/rock/blues split), so per the task brief we file
# the whole programme under the single `rock` category; the tag itself is
# the discriminator-that-isn't and is excluded from annotations (nothing
# else is present to carry there). See kami_club_SOURCE.md.
VENUE_SLUG = "kami-club"
EVENT_SOURCE_ID = "a1fbbfa7-8119-4fd6-a348-9f8df287ae45"
CATEGORY_SLUGS = ["rock"]
EXCLUDED_TAGS = {"live_music_other"}


def parse_feed(json_text: str, today: dt.date | None = None) -> list[ScrapedEvent]:
    return _esora_parse_feed(
        json_text,
        category_slugs=CATEGORY_SLUGS,
        excluded_tags=EXCLUDED_TAGS,
        today=today,
    )


class KamiClubScraper(EsoraFeedScraper):
    def __init__(self) -> None:
        super().__init__(
            venue_slug=VENUE_SLUG,
            event_source_id=EVENT_SOURCE_ID,
            category_slugs=CATEGORY_SLUGS,
            excluded_tags=EXCLUDED_TAGS,
        )


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
