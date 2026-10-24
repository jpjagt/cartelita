"""Theatre503 on the shared Spektrix helper, against saved API responses
(captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import theatre503 as t503

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / f"theatre503_spektrix_{name}.json").read_text())


def _scraped():
    events, instances = _load("events"), _load("instances")
    plans = _load("plans")  # plan id → [plan name, client venue name]
    for inst in instances:  # what spk.assign_plans gives each instance
        name, venue_name = plans.get(inst.get("planId"), ("", ""))
        inst["plan"], inst["venue"] = {"name": name}, {"name": venue_name}
    pages = spk.site_urls({u: set(ids) for u, ids in _load("site_ids").items()}, events, instances)
    selected = spk.select(events, instances, t503.categorize, t503.venue)
    return spk.build(t503.CLIENT, selected, {}, url=lambda e: pages.get(e["id"]), venue=t503.venue)


def test_writers_programme_masterclasses_dropped():
    events = _scraped()
    titles = {e.title for e in events}
    assert {"Boo!", "kat", "Mortal Sin", "Rapid Write Response: Boo!"} <= titles
    assert not any("Masterclass" in t for t in titles)
    assert all(e.category_slugs == ["theater"] for e in events)
    assert len({e.external_id for e in events}) == len(events)


def test_other_venues_dropped():
    def inst(plan, venue):
        return {"plan": {"name": plan}, "venue": {"name": venue}}

    assert t503.venue({}, inst("Cinema", "Battersea Power Station Cinema")) is None
    assert t503.venue({}, inst("Theatre503", "Theatre503")) == "theatre503"
    assert t503.venue({}, inst("Theatre503 Writers' Programme", "Theatre503")) is None
    assert t503.venue({}, {"plan": {}, "venue": {}}) is None


def test_show_pages_joined():
    by_title = {e.title: e.source_url for e in _scraped()}
    assert by_title["Boo!"] == "https://theatre503.com/whats-on/boo/"
