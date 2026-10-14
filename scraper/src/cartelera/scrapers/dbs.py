from __future__ import annotations

from cartelera.scrapers import _tribe_events as tribe
from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# dB's (Vlampijpstraat 63, Utrecht-Zuilen) — independent pop venue run by
# Stichting Ruis inside a rehearsal complex: punk, metal, garage, psych, indie.
# WordPress + The Events Calendar; we read its REST API (see
# _tribe_events.py and dbs_SOURCE.md). No price anywhere on the site (tickets
# are sold on Stager, which we don't touch) — price is None unless the event's
# own Tribe cost field says something (e.g. "Gratis").
SITE_URL = "https://dbstudio.nl"
VENUE_SLUG = "dbs"

# The venue's own event categories are genre labels plus a few house labels.
# Bar/café nights are not programme: the beer tap takeover, the quiz and the
# karaoke nights carry these labels.
NON_PROGRAMME = {
    "Karaoke",
    "PopPubQuiz Live",
    "Metal Quiz & Karaoke",
    "Tap Takeover",
    "Bier specials",
}
CAFE, CONCERT = "Cafe", "Concert"
# Labels that are not genres (don't count toward pop/alternative).
NEUTRAL = {CAFE, CONCERT}
# The venue's pop labels; every other label is an alternative-scene genre
# (punk, metal, garage, psych, noise, …) or a series name.
POP_LABELS = {"Pop", "Dream Pop", "Singer Song Writer"}


def is_programme(categories: list[str]) -> bool:
    cats = set(categories)
    if cats & NON_PROGRAMME:
        return False
    # A "Cafe" item without the Concert label is a bar night, not a show.
    return not (CAFE in cats and CONCERT not in cats)


def categorize(categories: list[str]) -> list[str]:
    labels = set(categories) - NEUTRAL
    pop = labels & POP_LABELS
    if pop and labels <= POP_LABELS:
        return ["pop"]
    if pop:
        return ["pop", "alternative"]
    return ["alternative"]


def parse_events(raw: list[dict]) -> list[ScrapedEvent]:
    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for ev in raw:
        title = tribe.title(ev)
        if not title or not ev.get("url"):
            continue
        categories = tribe.category_names(ev)
        if not is_programme(categories):
            continue
        external_id = str(ev["id"])
        if external_id in seen:
            continue
        seen.add(external_id)
        start_date, start_time = tribe.start(ev)
        annotations = [c for c in categories if c not in NEUTRAL] + [
            t for t in tribe.tag_names(ev) if t not in categories
        ]
        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=ev["url"],
                category_slugs=categorize(categories),
                price=tribe.cost_price(ev),
                image_url=tribe.image_url(ev),
                external_id=external_id,
                annotations=annotations,
            )
        )
    return events


class DbsScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return parse_events(tribe.fetch_all(SITE_URL))


register(
    scraper=DbsScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="dB's",
        city_slug="utrecht",
        address="Vlampijpstraat 63, 3534 AR Utrecht",
        site_url=SITE_URL,
        instagram_url="https://www.instagram.com/dbs_utrecht",
        category_slugs=["pop", "alternative"],
        list_memberships=[
            ListMembership(list_slug="pop", whitelist_category_slug="pop"),
            ListMembership(list_slug="alternative", whitelist_category_slug="alternative"),
        ],
    ),
)
