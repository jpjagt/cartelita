"""Cadogan Hall (Sloane Square) — home of the Royal Philharmonic Orchestra,
choral and early music, the London Jazz Festival; also a rental hall.

Spektrix client `cadoganhall` on tickets.cadoganhall.com, via the shared
`_spektrix` helper (see cadogan_hall_SOURCE.md). Curation on the box
office's own genre labels, `Genre1` (main) and `Genre2` (qualifier):

- Orchestra / Choral / Opera → classical; Family → classical + kids
  (orchestral family concerts); Jazz → jazz; Folk → folk; Film with
  Genre2 Orchestra (silent films with a live score) → film;
- Genre2 Tribute is dropped everywhere; so are Choral with Film (sing-along
  shows) or Gospel, and Jazz with Orchestra (an orchestral love-songs night);
- Pop, Rock / Country, Talk, Comedy, Musical Theatre, Dance, the Big Band
  film-music concert (Film / Big Band) and every unlabelled item (ancillaries:
  "Secure My Booking", programmes, prosecco, toys, VIP packages; also the
  unlabelled Out to Lunch foyer gigs) are dropped.

URLs: the event's `webUrl` (filled for most events; the hall's own show
page), else the Spektrix event page. No Site join: the what's-on page links
some dead show pages (404), which fail the shared join, and webUrl already
covers ~80% of what we keep.
"""

from __future__ import annotations

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "cadogan-hall"
CLIENT = spk.Client("cadoganhall", "https://tickets.cadoganhall.com")

GENRE1: dict[str, list[str]] = {
    "Orchestra": ["classical"],
    "Choral": ["classical"],
    "Opera": ["classical"],
    "Family": ["classical", "kids"],
    "Jazz": ["jazz"],
    "Folk": ["folk"],
}
# (Genre1, Genre2) pairs that are not the programme the Genre1 suggests.
EXCLUDED_PAIRS = {("Choral", "Film"), ("Choral", "Gospel"), ("Jazz", "Orchestra")}


def categorize(event: dict) -> list[str]:
    g1, g2 = spk.attr(event, "Genre1"), spk.attr(event, "Genre2")
    if g2 == "Tribute" or (g1, g2) in EXCLUDED_PAIRS:
        return []
    if g1 == "Film":
        return ["film"] if g2 == "Orchestra" else []
    return list(GENRE1.get(g1, []))


def web_url(event: dict) -> str | None:
    return (event.get("webUrl") or "").strip() or None


class CadoganHallScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return spk.scrape(CLIENT, categorize, url=web_url)


register(
    scraper=CadoganHallScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Cadogan Hall",
        city_slug="london",
        address="5 Sloane Terrace, London SW1X 9DQ",
        site_url="https://cadoganhall.com",
        instagram_url="https://www.instagram.com/cadoganhall",
        category_slugs=["classical", "jazz", "folk", "kids", "film"],
        list_memberships=[
            ListMembership(list_slug=cat, whitelist_category_slug=cat)
            for cat in ("classical", "jazz", "folk", "kids", "film")
        ],
    ),
)
