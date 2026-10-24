"""The London venues built on the shared Spektrix helper, against saved API
responses (events + two weeks of instances, captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import little_angel_theatre, polka, soho_theatre

FIXTURES = Path(__file__).parent / "fixtures"


def _programme(stem: str, module, venue=None, plan_venues=False):
    events = json.loads((FIXTURES / f"{stem}_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / f"{stem}_spektrix_instances.json").read_text())
    if plan_venues:
        by_plan = json.loads((FIXTURES / f"{stem}_spektrix_plan_venues.json").read_text())
        for inst in instances:
            inst["venue"] = by_plan.get(inst.get("planId"), {})
    selected = spk.select(events, instances, module.categorize, venue)
    return spk.build(module.CLIENT, selected, {}, venue=venue)


def test_polka_keeps_shows_only():
    events = _programme("polka", polka)
    titles = {e.title for e in events}
    assert titles == {"Toto", "At Sea", "The Sleep Show", "You'll See"}
    joined = " ".join(titles)
    for dropped in ("Ice Cream Pre-Order", "Secure My Booking", "Touch Tour", "Family Storytime"):
        assert dropped not in joined
    assert all(e.category_slugs == ["kids"] for e in events)
    assert len({e.external_id for e in events}) == len(events)


def test_little_angel_keeps_in_house_shows_incl_relaxed():
    events = _programme("little_angel_theatre", little_angel_theatre,
                        venue=little_angel_theatre.venue, plan_venues=True)
    titles = {e.title for e in events}
    assert "The Pied Piper: A Rat's Tale" in titles
    joined = " ".join(titles)
    assert "Family Workshops" not in joined and "Puppet Playcation" not in joined
    assert "Hands On" not in joined
    assert all(e.category_slugs == ["kids"] for e in events)
    # The seating plan says which building: the Pied Piper plays the Studios.
    by_title = {e.title: e.venue_slug for e in events}
    assert by_title["The Pied Piper: A Rat's Tale"] == "little-angel-studios"
    assert by_title["Pip and Posy Live on Stage"] == "little-angel-theatre"


def test_soho_theatre_and_family_by_room():
    events = _programme("soho_theatre", soho_theatre, venue=soho_theatre.venue)
    cats = {tuple(e.category_slugs) for e in events}
    assert cats == {("theater",), ("kids",)}
    assert {e.venue_slug for e in events} == {"soho-theatre", "soho-theatre-walthamstow"}
    # Comedy (most of the client's volume) and the Glasgow Glee Club are out.
    raw = json.loads((FIXTURES / "soho_theatre_spektrix_events.json").read_text())
    comedy = {e["id"] for e in raw if e.get("attribute_WebsiteFilterCategory1") == "Comedy"}
    kept_events = {e.source_url for e in events}
    assert not any(spk.numeric_id(i) in url for i in comedy for url in kept_events)
    family = [e for e in events if e.category_slugs == ["kids"]]
    assert family and all(e.venue_slug == "soho-theatre-walthamstow" for e in family)


def test_soho_rooms_map_to_venues():
    assert soho_theatre.venue({"attribute_Venue": "Upstairs"}, {}) == "soho-theatre"
    assert soho_theatre.venue({"attribute_Venue": "Glasgow Glee Club"}, {}) is None
    assert soho_theatre.categorize(
        {"attribute_Venue": "Glasgow Glee Club", "attribute_WebsiteFilterCategory1": "Theatre"}
    ) == []
