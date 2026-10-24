"""Royal Academy of Music on the shared Spektrix helper, against saved API
responses and the event pages' Spektrix ids (captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import royal_academy_of_music as ram

FIXTURES = Path(__file__).parent / "fixtures"


def _scraped():
    events = json.loads((FIXTURES / "royal_academy_of_music_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "royal_academy_of_music_spektrix_instances.json").read_text())
    by_plan = json.loads((FIXTURES / "royal_academy_of_music_spektrix_plan_venues.json").read_text())
    page_ids = json.loads((FIXTURES / "royal_academy_of_music_spektrix_site_ids.json").read_text())
    for inst in instances:
        inst["venue"] = by_plan.get(inst.get("planId"), {})
    pages = spk.site_urls({u: set(ids) for u, ids in page_ids.items()}, events, instances)
    # Site(required=True): only events with a page on ram.ac.uk.
    def listed(event):
        return ram.categorize(event) if event["id"] in pages else []

    selected = spk.select(events, instances, listed, ram.venue)
    return spk.build(ram.CLIENT, selected, {}, url=lambda e: pages.get(e["id"]), venue=ram.venue)


def test_only_events_the_academy_lists():
    scraped = _scraped()
    titles = {e.title for e in scraped}
    assert {"Trio Avant", "A Play Of Passion", "Masterclass: Susan Bullock"} <= titles
    # Printed programmes are sold per opera performance, never listed.
    assert "Programme" not in titles
    assert all(e.category_slugs == ["classical"] for e in scraped)
    assert {e.venue_slug for e in scraped} == {"royal-academy-of-music"}
    assert len({e.external_id for e in scraped}) == len(scraped)


def test_events_link_to_their_academy_page():
    by_title = {e.title: e.source_url for e in _scraped()}
    assert by_title["Trio Avant"] == "https://www.ram.ac.uk/events/trio-avant"
    assert by_title["Masterclass: Véronique Gens"] == "https://www.ram.ac.uk/events/masterclass-véronique-gens"


def test_partner_venues_dropped():
    assert ram.venue({}, {"venue": {"name": "Wigmore Hall"}}) is None
    assert ram.venue({}, {"venue": {"name": "Royal Academy of Music"}}) == "royal-academy-of-music"
    assert ram.categorize({"attribute_Venue": "Duke's Hall"}) == ["classical"]
    assert ram.categorize({}) == []
