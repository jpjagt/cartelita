"""Donmar Warehouse on the Spektrix helper, against saved API responses
(captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import donmar_warehouse

FIXTURES = Path(__file__).parent / "fixtures"


def test_keeps_performances_drops_development_events():
    events = json.loads((FIXTURES / "donmar_warehouse_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "donmar_warehouse_spektrix_instances.json").read_text())
    out = spk.build(donmar_warehouse.CLIENT,
                    spk.select(events, instances, donmar_warehouse.categorize), {})
    assert {e.title for e in out} == {"ILFORD BOY", "THE KING'S RANSOM", "NO MAN'S LAND"}
    assert all(e.category_slugs == ["theater"] for e in out)
    assert len({e.external_id for e in out}) == len(out)
    joined = " ".join(e.title for e in out)
    assert "Script Conversation" not in joined and "Test Event" not in joined


def test_event_pages_from_the_search_index_by_exact_name():
    docs = json.loads((FIXTURES / "donmar_warehouse_search.json").read_text())
    pages = spk.search_title_pages(docs, donmar_warehouse.INDEX)
    assert pages[spk.title_key("ILFORD BOY")] == "https://www.donmarwarehouse.com/events/ilford-boy"
    assert pages[spk.title_key("THE KING'S RANSOM")] == "https://www.donmarwarehouse.com/events/the-kings-ransom"
