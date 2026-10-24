"""Orange Tree Theatre on the shared Spektrix helper, against saved API
responses (captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import orange_tree_theatre as ot

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / f"orange_tree_theatre_spektrix_{name}.json").read_text())


def _scraped():
    events, instances = _load("events"), _load("instances")
    by_plan = _load("plan_venues")
    for inst in instances:
        inst["venue"] = by_plan.get(inst.get("planId"), {})
    return spk.build(ot.CLIENT, spk.select(events, instances, ot.categorize, ot.venue), {}, venue=ot.venue)


def test_plays_kept_everything_else_dropped():
    events = _scraped()
    titles = {e.title for e in events}
    assert {"King Lear", "Richard II", "The Vortex", "a small and quiet light"} <= titles
    joined = " | ".join(titles)
    for dropped in ("OT On Screen", "Saturday Seminar", "Acting Lab", "WORKSHOPS",
                    "St Mary Magdalene", "Coffee Concert", "Shakespeare Up Close"):
        assert dropped not in joined
    assert all(e.category_slugs == ["theater"] for e in events)
    assert all(e.venue_slug == "orange-tree-theatre" for e in events)
    assert len({e.external_id for e in events}) == len(events)


def test_off_site_production_dropped_by_plan():
    # "Murder in the Cathedral: OT in the Church" is a Classical Play, but
    # plays St John the Divine (its own plan/venue).
    assert "Murder in the Cathedral: OT in the Church" not in {e.title for e in _scraped()}
    assert ot.venue({}, {"venue": {"name": "St John's"}}) is None
