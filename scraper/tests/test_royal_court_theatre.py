"""Royal Court Theatre on the Spektrix helper, against saved API responses and
the Spektrix ids its show pages embed (captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import royal_court_theatre as rc

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / f"royal_court_theatre_{name}.json").read_text())


def _programme():
    events, instances = _load("spektrix_events"), _load("spektrix_instances")
    page_ids = {url: set(ids) for url, ids in _load("site_ids").items()}
    pages = spk.site_urls(page_ids, events, instances)
    # What spk.scrape does for Site(required=True): only listed events.
    categorize = lambda e: rc.categorize(e) if e["id"] in pages else []  # noqa: E731
    selected = spk.select(events, instances, categorize)
    return spk.build(rc.CLIENT, selected, {}, url=lambda e: pages.get(e["id"]))


def test_keeps_listed_shows_in_the_two_auditoriums():
    events = _programme()
    assert {e.title for e in events} == {"Blood of my Blood", "Monument", "The Afronauts"}
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


def test_unpublished_shows_wait_for_their_page():
    # Purpose / The Apology are in the box office but not yet on the website.
    titles = {e.title for e in _programme()}
    assert "Purpose" not in titles and "The Apology" not in titles
