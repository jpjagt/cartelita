"""Royal Academy of Music (Marylebone) — conservatoire concerts, opera and
masterclasses, many of them free.

Spektrix client `royalacademyofmusic` on ticketing.ram.ac.uk, via the shared
`_spektrix` helper (see royal_academy_of_music_SOURCE.md). The client's only
event attribute is `Venue` (the room: Duke's Hall, Angela Burgess Recital
Hall, Susie Sainsbury Theatre, Concert Room…), which doesn't separate the
programme from ancillaries ("Programme": printed programmes sold per opera
performance). So curation is the Academy's own website: only events the
site lists are kept. The what's-on page renders its list by script from the
site's search index (Typesense; `spk.SearchIndex`), whose event documents
carry the event page (`/events/<slug>`) and the Spektrix id the page was
imported from — the join, without fetching ram.ac.uk itself (Cloudflare
challenges the production server there).

The building comes from the seating plan → the client's venue: only "Royal
Academy of Music" is kept (the client also sells at Wigmore Hall, St John's
Smith Square, Snape Maltings, Southbank Centre… — partner venues).
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "royal-academy-of-music"
CLIENT = spk.Client("royalacademyofmusic", "https://ticketing.ram.ac.uk")
INDEX = spk.SearchIndex("ram_main_production", "https://www.ram.ac.uk")
CLIENT_VENUE = "Royal Academy of Music"


def categorize(event: dict) -> list[str]:
    return ["classical"] if spk.attr(event, "Venue") else []


def venue(event: dict, instance: dict) -> str | None:
    return VENUE_SLUG if (instance.get("venue") or {}).get("name") == CLIENT_VENUE else None


class RoyalAcademyOfMusicScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        page_ids = spk.search_page_ids(spk.search_events(INDEX), INDEX)
        return spk.scrape(CLIENT, categorize, page_ids=page_ids, listed_only=True,
                          venue=venue, plan_venues=True)


register(
    scraper=RoyalAcademyOfMusicScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Royal Academy of Music",
        city_slug="london",
        address="Marylebone Road, London NW1 5HT",
        site_url="https://www.ram.ac.uk",
        instagram_url="https://www.instagram.com/royalacademyofmusic",
        category_slugs=["classical"],
        list_memberships=[ListMembership(list_slug="classical")],
    ),
)
