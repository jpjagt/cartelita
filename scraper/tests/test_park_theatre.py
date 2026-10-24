"""Park Theatre on the shared Spektrix helper, against saved API responses
(captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import park_theatre as park

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / f"park_theatre_spektrix_{name}.json").read_text())


def _scraped():
    events, instances = _load("events"), _load("instances")
    pages = spk.site_urls({u: set(ids) for u, ids in _load("site_ids").items()}, events, instances)
    return spk.build(park.CLIENT, spk.select(events, instances, park.categorize), {},
                     url=lambda e: pages.get(e["id"]))


def test_supplementary_events_and_stand_up_dropped():
    events = _scraped()
    titles = {e.title for e in events}
    assert {"The Pianist", "Mojo", "Spitfire Girls", "Dickens' Christmas"} <= titles
    joined = " | ".join(titles)
    for dropped in ("Pizzas", "Drinks", "Programme", "Cast Album", "Touch Tour",
                    "headset", "Captioning", "Sami Abu Wardeh"):
        assert dropped not in joined
    assert len({e.external_id for e in events}) == len(events)


def test_family_recommendation_is_kids():
    by_title = {e.title: e.category_slugs for e in _scraped()}
    assert by_title["Comedy Club 4 Kids"] == ["kids"]
    assert by_title["The Pianist"] == ["theater"]
    assert by_title["Miss Bennet: Christmas at Pemberley"] == ["theater"]


def test_rooms_outside_the_building_dropped():
    assert park.categorize({"attribute_Genre": "Drama", "attribute_Venue": "Events Elsewhere"}) == []
    assert park.categorize({"attribute_Genre": "Drama", "attribute_Venue": "Park90"}) == ["theater"]


def test_site_page_preferred():
    by_title = {e.title: e.source_url for e in _scraped()}
    assert by_title["Mojo"] == "https://parktheatre.co.uk/events/mojo/"
