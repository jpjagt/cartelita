import datetime as dt
from pathlib import Path

from cartelera.scrapers.pantomime_theatre import VENUE_SLUG, parse_feed

FIXTURES = Path(__file__).parent / "fixtures"
EMPTY_FIXTURE = FIXTURES / "pantomime_theatre_feed_empty.json"
POPULATED_FIXTURE = FIXTURES / "pantomime_theatre_feed_populated.json"

# The empty fixture is the live feed as fetched 2026-08-19 (dormant — see
# pantomime_theatre_SOURCE.md); the populated fixture is synthetic, built in
# the same esora feed shape, exercising the happy path since the live feed
# has no upcoming events today.
TODAY = dt.date(2026, 8, 19)


def test_empty_feed_returns_no_events_without_error():
    assert parse_feed(EMPTY_FIXTURE.read_text(), today=TODAY) == []


def test_populated_feed_yields_theater_category():
    events = parse_feed(POPULATED_FIXTURE.read_text(), today=TODAY)
    assert len(events) == 1
    assert events[0].category_slugs == ["theater"]
    assert events[0].title == "Պիերոյի երազը"
    assert events[0].external_id == "esora-occ-occ-1"


def test_scraper_registered():
    from cartelera.scrapers import REGISTRY
    import cartelera.scrapers.pantomime_theatre  # noqa: F401 (trigger register)

    assert VENUE_SLUG in REGISTRY, f"Scraper {VENUE_SLUG!r} not in REGISTRY"
    scraper, source = REGISTRY[VENUE_SLUG]
    assert scraper.venue_slug == VENUE_SLUG
    (venue_def,) = source.venues
    assert venue_def.slug == "pantomime-theatre"
    assert venue_def.city_slug == "yerevan"
    assert venue_def.category_slugs == ["theater"]
    assert [m.list_slug for m in venue_def.list_memberships] == ["theater"]
