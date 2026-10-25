"""Royal Court Theatre on the Spektrix helper, against saved API responses
(captured 2026-10-24) and the site's search-index event documents (captured
2026-10-25)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import royal_court_theatre as rc

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / f"royal_court_theatre_{name}.json").read_text())


def _programme():
    events, instances = _load("spektrix_events"), _load("spektrix_instances")
    listing = rc.Listing(spk.search_title_pages(_load("search"), rc.INDEX))
    selected = spk.select(events, instances, listing.categorize)
    return spk.build(rc.CLIENT, selected, {}, url=listing.url)


def test_keeps_listed_shows_in_the_two_auditoriums():
    events = _programme()
    # Man to Man (final performance on the fixture's day) too: its show page
    # dropped the booking ids on the last day, the search index still lists it.
    assert {e.title for e in events} == {"Blood of my Blood", "Monument", "The Afronauts", "Man to Man"}
    assert all(e.category_slugs == ["theater"] for e in events)
    assert all(e.source_url.startswith("https://royalcourttheatre.com/events/") for e in events)
    assert len({e.external_id for e in events}) == len(events)


def test_drops_tests_tours_talks_and_off_site():
    joined = " ".join(e.title for e in _programme())
    # Tests and touch tours sit in the main rooms but no show page lists them.
    for dropped in ("Test", "Touch Tour", "Book Club", "First Words", "Writers' Card",
                    "Backstage Tour", "Bowling", "May Fair", "Directors' Night"):
        assert dropped not in joined
    # Listed on the site but not in an auditorium: dropped by the room.
    assert rc.categorize({"attribute_TicketVenue1": "Balcony Bar"}) == []
    assert rc.categorize({"attribute_TicketVenue1": "Jerwood Theatre Upstairs"}) == ["theater"]


def test_listing_join_is_the_exact_name():
    listing = rc.Listing({"the afronauts": "https://royalcourttheatre.com/events/afronauts"})
    room = {"attribute_TicketVenue1": "Jerwood Theatre Downstairs"}
    assert listing.url({"name": "The  Afronauts"}) == "https://royalcourttheatre.com/events/afronauts"
    assert listing.categorize({**room, "name": "THE AFRONAUTS"}) == ["theater"]
    # Never fuzzy: the touch tour and a test event are other names.
    assert listing.categorize({**room, "name": "The Afronauts - Touch Tour"}) == []
    assert listing.categorize({**room, "name": "Afronauts Test"}) == []


def test_unpublished_shows_wait_for_their_page():
    # Purpose / The Apology are in the box office but not yet on the website.
    titles = {e.title for e in _programme()}
    assert "Purpose" not in titles and "The Apology" not in titles
