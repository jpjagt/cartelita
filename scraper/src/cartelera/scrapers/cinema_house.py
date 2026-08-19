from __future__ import annotations

from cartelera.ig.source import IgProfileScraper, IgSourceConfig
from cartelera.scrapers import register
from cartelera.types import ListMembership, SourceDefinition, VenueDefinition

# Cinema House (Կինոյի տուն) — the Union of Film Professionals of Armenia's own
# house on Vardanants St: three halls (500/120/80 seats, renovated 2018),
# retrospectives, archival programmes and festival hosting (Golden Apricot).
# The Filmoteca analogue for Yerevan.
#
# It has no scrapeable listing anywhere: no site of its own, an esora source
# page with zero upcoming occurrences, a tomsarkgh venue page with no events,
# nothing on ticket-am/toms.am. Its programme is announced only on Instagram,
# so this is an IG source — a thin config over cartelera/ig (capture the
# profile, parse each post once with a vision LLM, emit gated events every
# night). See cinema_house_SOURCE.md for the recon ladder, the field map and
# the (pending) live verification.
VENUE_SLUG = "cinema-house"
HANDLE = "cinemahouse.evn"

HINTS = (
    "Yerevan's cinematheque (Union of Film Professionals). Posts announce film "
    "screenings, retrospectives, archival and restored programmes, director "
    "Q&As and hosted festivals (Golden Apricot in July). Captions and flyers "
    "are in Armenian, sometimes Russian or English; the flyer usually carries "
    "the film title, the date and the screening time, and a retrospective "
    "flyer may list several dated screenings at once — emit one event per "
    "screening. Screening-language notes (dubbed/subtitled) belong in "
    "`language`, never in the title."
)

VENUE = VenueDefinition(
    slug=VENUE_SLUG,
    name="Cinema House",
    city_slug="yerevan",
    address="18/1 Vardanants St, Yerevan",
    site_url=None,  # unikino.am / uca.am do not resolve
    instagram_url=f"https://www.instagram.com/{HANDLE}/",
    category_slugs=["film"],
    list_memberships=[ListMembership(list_slug="film")],
)

CONFIG = IgSourceConfig(
    handle=HANDLE,
    # The same 1:1 source register() builds below, derived from the venue so
    # the roster the model sees and the runner's whitelist cannot drift apart.
    source=SourceDefinition(slug=VENUE.slug, name=VENUE.name, venues=[VENUE]),
    canonical_lang="hy",
    hints_by_venue={VENUE_SLUG: HINTS},
)

register(scraper=IgProfileScraper(CONFIG), venue=VENUE)
