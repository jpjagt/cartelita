"""Bush Theatre on the Spektrix helper, against saved API responses (captured
2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import bush_theatre

FIXTURES = Path(__file__).parent / "fixtures"


def _programme():
    events = json.loads((FIXTURES / "bush_theatre_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "bush_theatre_spektrix_instances.json").read_text())
    return spk.build(bush_theatre.CLIENT, spk.select(events, instances, bush_theatre.categorize), {})


def test_keeps_productions_only():
    events = _programme()
    assert {e.title for e in events} == {
        "Darkling", "The Hungry Ghost", "The Bridge", "ATTENTION", "Global Majority",
        "Ripples", "Insane Asylum Seekers",
    }
    # Darkling's cancelled performance is dropped, its other one kept.
    assert sum(e.title == "Darkling" for e in events) == 1
    joined = " ".join(e.title for e in events)
    for dropped in ("Pre-order Drinks", "Headset", "Captioning Facilities", "Touch Tour"):
        assert dropped not in joined
    assert all(e.category_slugs == ["theater"] for e in events)
    assert len({e.external_id for e in events}) == len(events)
    assert all(e.source_url.startswith("https://tickets.bushtheatre.co.uk/bushtheatre/") for e in events)
