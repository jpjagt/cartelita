from __future__ import annotations

from cartelera.ig.source import IgProfileScraper, IgSourceConfig
from cartelera.scrapers import register
from cartelera.types import ListMembership, SourceDefinition, VenueDefinition

# Mezzo Classic House Club (28 Isahakyan St, Yerevan) — an upscale two-storey
# live-music club: classical recitals and jazz, plus blues, rock, latin and
# folk nights, live music every evening. A multi-category venue on the
# Jamboree pattern: it sits in three lists, each whitelisted to one category,
# so its nights split correctly instead of flooding one list.
#
# It is web-dark: mezzo.am is domain-squatted, it is absent from all ~1,400
# esora Yerevan sources, and tomsarkgh only carries a restaurant-reservation
# profile with no dated events. The programme is announced on Instagram, so
# this is an IG source — a thin config over cartelera/ig (capture the profile,
# parse each post once with a vision LLM, emit gated events every night). The
# handle is VERIFIED from non-Instagram sources; see mezzo_SOURCE.md for that
# evidence, the recon ladder, the field map and the (pending) live
# verification.
VENUE_SLUG = "mezzo"
HANDLE = "mezzoclub"

HINTS = (
    "Live-music club: classical recitals, jazz sets, and blues/rock/latin/folk "
    "nights, one or more acts every evening. Posts are usually the night's "
    "programme (band or performer name, date, start time, cover price) and "
    "flyers sometimes list a whole week — emit one event per date, never one "
    "per post. Captions and flyers are in Armenian, often Russian, sometimes "
    "English. Choose `category` from what the act plays: `classical` for "
    "recitals and chamber programmes, `jazz` for jazz/latin/funk/ethno-jazz, "
    "`rock` for rock, blues and pop-rock bands. Dinner/reservation and "
    "birthday-party promotions are not events."
)

VENUE = VenueDefinition(
    slug=VENUE_SLUG,
    name="Mezzo Classic House Club",
    city_slug="yerevan",
    address="28 Isahakyan St, Yerevan",
    site_url=None,  # mezzo.am is domain-squatted (Sedo parking), not the venue
    instagram_url=f"https://www.instagram.com/{HANDLE}/",
    category_slugs=["classical", "jazz", "rock"],
    list_memberships=[
        ListMembership(list_slug="classical", whitelist_category_slug="classical"),
        ListMembership(list_slug="jazz", whitelist_category_slug="jazz"),
        ListMembership(list_slug="rock", whitelist_category_slug="rock"),
    ],
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
