"""Young Vic on the Spektrix helper, against saved API responses (captured
2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import young_vic

FIXTURES = Path(__file__).parent / "fixtures"


def _programme():
    events = json.loads((FIXTURES / "young_vic_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "young_vic_spektrix_instances.json").read_text())
    return spk.build(young_vic.CLIENT, spk.select(events, instances, young_vic.categorize), {})


def test_keeps_productions_in_the_rooms():
    events = _programme()
    assert {e.title for e in events} == {
        "THELMA & LOUISE", "GIRLS", "EUROTRASH", "LA DISTANCE", "DISSENT", "EULOGY",
        "WHAT'S THE F**KING POINT?",
    }
    assert all(e.category_slugs == ["theater"] for e in events)
    assert len({e.external_id for e in events}) == len(events)
    assert all("youngvic/website/EventDetails.aspx?EventId=" in e.source_url for e in events)


def test_drops_supplementary_and_room_less_events():
    joined = " ".join(e.title for e in _programme())
    for dropped in ("programme", "Programme", "Playtext", "Headset", "listening device",
                    "Touch Tour", "Temporary Priority Test"):
        assert dropped not in joined
    # A programme carries the show's room but is flagged supplementary.
    assert young_vic.categorize(
        {"attribute_Venue": "Main House", "attribute_SupplementaryEvent": True}
    ) == []
