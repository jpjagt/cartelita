"""The Yard Theatre on the shared Spektrix helper, against saved API
responses (captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import the_yard_theatre as yard

FIXTURES = Path(__file__).parent / "fixtures"


def _scraped():
    events = json.loads((FIXTURES / "the_yard_theatre_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "the_yard_theatre_spektrix_instances.json").read_text())
    return spk.build(yard.CLIENT, spk.select(events, instances, yard.categorize), {})


def test_events_with_a_public_page_kept():
    events = _scraped()
    titles = {e.title for e in events}
    assert {"Lear", "Mrs Dalloway", "Live Drafts: Coming Home"} <= titles
    assert "Lear: The Gala" not in titles  # fundraiser: no public page
    assert all(e.source_url.startswith("https://www.theyardtheatre.co.uk/events/") for e in events)
    assert all(e.category_slugs == ["theater"] for e in events)
    assert len({e.external_id for e in events}) == len(events)


def test_web_url_must_be_a_show_page():
    assert yard.categorize({"webUrl": ""}) == []
    assert yard.categorize({"webUrl": "https://www.theyardtheatre.co.uk/support-us"}) == []
    assert yard.categorize({"webUrl": "https://www.theyardtheatre.co.uk/events/lear"}) == ["theater"]
