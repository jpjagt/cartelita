"""Kiln Theatre on the Spektrix helper, against saved API responses (captured
2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import kiln_theatre

FIXTURES = Path(__file__).parent / "fixtures"


def _programme():
    events = json.loads((FIXTURES / "kiln_theatre_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "kiln_theatre_spektrix_instances.json").read_text())
    return spk.build(kiln_theatre.CLIENT, spk.select(events, instances, kiln_theatre.categorize), {})


def test_theatre_and_cinema_by_type():
    events = _programme()
    cats = {e.title: e.category_slugs for e in events}
    assert cats["NINE NIGHT"] == ["theater"]
    assert cats["BERLIN"] == ["theater"]
    assert cats["Wild Horse Nine"] == ["film"]
    assert cats["NT Live: Golden Boy"] == ["film"]  # event cinema is Kiln Cinema's
    assert {tuple(c) for c in cats.values()} == {("theater",), ("film",)}
    assert len({e.external_id for e in events}) == len(events)


def test_drops_add_ons_and_hires():
    joined = " ".join(e.title for e in _programme())
    assert "Audio Description Add-ons" not in joined  # WebEventType says Theatre
    assert "Raising Hare" not in joined  # External Hire
