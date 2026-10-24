"""London gig and club venues that sell on DICE, via the shared `_dice` helper.

Each venue is its own source (per-venue health), registered from the table
below. The category comes from DICE's own type tag (`music:gig`,
`music:dj`, `music:party`), mapped per venue to the list it belongs on;
types a venue doesn't map (comedy, quizzes, socials — and DJ/party nights
at gig venues) are dropped. Venues that publish their own DICE widget key
(MOTH Club, Strongroom) are read through it, which adds genre tags: a gig
tagged with a rock or folk genre goes to that list instead. See
dice_london_SOURCE.md.
"""

from __future__ import annotations

from cartelera.scrapers import _dice as dice
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

GIG = "music:gig"
DJ = "music:dj"
PARTY = "music:party"

# Genre refinement for key-mode venues: DICE genre tags → our category.
ROCK_GENRES = {
    f"gig:{g}" for g in (
        "rock", "punk", "postpunk", "art_punk", "hardcore", "metal", "garagerock",
        "noiserock", "alt_rock", "indierock", "rocknroll", "progressiverock",
    )
}
FOLK_GENRES = {f"gig:{g}" for g in ("folk", "folkrock", "folkpop")}
GENRES = {**{g: "rock" for g in ROCK_GENRES}, **{g: "folk" for g in FOLK_GENRES}}


class DiceVenueScraper:
    def __init__(self, venue: dice.Venue):
        self.venue = venue
        self.venue_slug = venue.slug

    def scrape(self) -> list[ScrapedEvent]:
        return dice.scrape(self.venue)


def _venue(
    slug: str,
    name: str,
    address: str,
    site_url: str | None,
    dice_name: str,
    page: str,
    types: dict[str, str],
    *,
    api_key: str | None = None,
    key_origin: str | None = None,
) -> None:
    cats = list(dict.fromkeys(types.values()))
    if api_key:
        cats += [c for c in ("rock", "folk") if c not in cats and types.get(GIG) == "pop"]
    whitelist = len(cats) > 1
    register(
        scraper=DiceVenueScraper(
            dice.Venue(
                slug=slug, dice_name=dice_name, page=page, types=types,
                genres=GENRES if api_key and types.get(GIG) == "pop" else {},
                api_key=api_key, key_origin=key_origin,
            )
        ),
        venue=VenueDefinition(
            slug=slug,
            name=name,
            city_slug="london",
            address=address,
            site_url=site_url,
            category_slugs=cats,
            list_memberships=[
                ListMembership(list_slug=c, whitelist_category_slug=c if whitelist else None)
                for c in cats
            ],
        ),
    )


# --- club ---
_venue("phonox", "Phonox", "418 Brixton Road, London SW9 7AY", "https://www.phonox.co.uk",
       "Phonox", "phonox-zd8e", {DJ: "club", PARTY: "club"})
_venue("colour-factory", "Colour Factory", "Queen's Yard, London E9 5EN", None,
       "Colour Factory", "colour-factory-z6v7", {DJ: "club", PARTY: "club", GIG: "alternative"})
_venue("fold", "FOLD", "Gillian House, Stephenson Street, London E16 4SA", "https://fold.london",
       "FOLD", "fold-q5ka", {DJ: "club", PARTY: "club"})
_venue("village-underground", "Village Underground", "54 Holywell Lane, London EC2A 3PQ",
       "https://villageunderground.co.uk", "Village Underground", "village-underground-wwop",
       {DJ: "club", PARTY: "club", GIG: "pop"})

# --- pop (indie gigs) ---
_venue("moth-club", "MOTH Club", "Old Trades Hall, Valette Street, London E9 6NU",
       "https://mothclub.co.uk", "MOTH Club", "moth-club-43ox", {GIG: "pop"},
       api_key="t7ohtz7EWk3gjVx2PNQafaYhqYoG5N1e1lJ5EbTq", key_origin="https://mothclub.co.uk/")
_venue("the-lexington", "The Lexington", "96-98 Pentonville Road, London N1 9JB",
       "https://www.thelexington.co.uk", "The Lexington", "the-lexington-jomz", {GIG: "pop"})
_venue("oslo-hackney", "Oslo Hackney", "1a Amhurst Road, London E8 1LL", None,
       "Oslo Hackney", "oslo-hackney-je6z", {GIG: "pop"})
_venue("the-shacklewell-arms", "The Shacklewell Arms", "71 Shacklewell Lane, London E8 2EB",
       "https://www.shacklewellarms.com", "The Shacklewell Arms", "the-shacklewell-arms-z82z", {GIG: "pop"})
_venue("paper-dress-vintage", "Paper Dress Vintage", "352a Mare Street, London E8 1HR",
       "https://www.paperdressvintage.co.uk", "Paper Dress Vintage", "paper-dress-vintage-ja37", {GIG: "pop"})
_venue("sebright-arms", "Sebright Arms", "31-35 Coate Street, London E2 9AG",
       "https://www.sebrightarms.com", "Sebright Arms", "sebright-arms-4mm9", {GIG: "pop"})
_venue("the-old-blue-last", "The Old Blue Last", "38 Great Eastern Street, London EC2A 3ES", None,
       "The Old Blue Last", "the-old-blue-last-4ryw", {GIG: "pop"})
_venue("islington-assembly-hall", "Islington Assembly Hall", "Upper Street, London N1 2UD",
       "https://islingtonassemblyhall.co.uk", "Islington Assembly Hall", "islington-assembly-hall-z8e2",
       {GIG: "pop"})
_venue("union-chapel", "Union Chapel", "Compton Terrace, London N1 2UN", "https://www.unionchapel.org.uk",
       "Union Chapel", "union-chapel-jx9a", {GIG: "pop"})

# --- rock ---
_venue("the-100-club", "The 100 Club", "100 Oxford Street, London W1D 1LL", "https://www.the100club.co.uk",
       "The 100 Club", "the-100-club-z997", {GIG: "rock"})
_venue("the-george-tavern", "The George Tavern", "373 Commercial Road, London E1 0LA",
       "https://www.thegeorgetavern.co.uk", "The George Tavern", "the-george-tavern-kx88", {GIG: "rock"})
_venue("the-black-heart", "The Black Heart", "2-3 Greenland Place, London NW1 0AP", None,
       "The Black Heart", "the-black-heart-4bev", {GIG: "rock"})
_venue("electric-ballroom", "Electric Ballroom", "184 Camden High Street, London NW1 8QP",
       "https://www.electricballroom.co.uk", "Electric Ballroom", "electric-ballroom-j78v", {GIG: "rock"})
_venue("windmill-brixton", "Windmill Brixton", "22 Blenheim Gardens, London SW2 5BZ",
       "https://windmillbrixton.co.uk", "Windmill Brixton", "windmill-brixton-jxdl", {GIG: "rock"})

# --- alternative ---
_venue("earth-hackney", "EartH", "11-17 Stoke Newington Road, London N16 8BH", "https://earthackney.co.uk",
       "EartH", "earth-76a7", {GIG: "alternative"})
_venue("strongroom", "Strongroom", "120-124 Curtain Road, London EC2A 3SQ", "https://www.strongroombar.com",
       "Strongroom", "strongroom-4bym", {GIG: "alternative"},
       api_key="ZaR9o0SyEM2ydlal1nWxJ7Jwkjn1bxh39Rljkmxi", key_origin="https://www.strongroombar.com/")

# --- folk / global ---
_venue("hootananny-brixton", "Hootananny Brixton", "95 Effra Road, London SW2 1DF",
       "https://www.hootanannybrixton.co.uk", "Hootananny Brixton", "hootananny-brixton-parp", {GIG: "folk"})

# --- jazz ---
_venue("ninety-one-living-room", "91 Living Room", "91 Brick Lane, London E1 6QL", "https://91livingroom.com",
       "Ninety One ", "ninety-one-6pob", {GIG: "jazz"})
