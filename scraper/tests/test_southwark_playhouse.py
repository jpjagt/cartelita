"""Southwark Playhouse on the shared Spektrix helper, against saved API
responses and production-page ids (captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import southwark_playhouse as sp

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / f"southwark_playhouse_spektrix_{name}.json").read_text())


def _scraped():
    events, instances = _load("events"), _load("instances")
    by_plan = _load("plan_venues")
    for inst in instances:
        inst["venue"] = by_plan.get(inst.get("planId"), {})
    pages = spk.site_urls({u: set(ids) for u, ids in _load("site_ids").items()}, events, instances)
    listed = lambda e: sp.categorize(e) if e["id"] in pages else []  # noqa: E731 (Site required)
    selected = spk.select(events, instances, listed, sp.venue)
    return spk.build(sp.CLIENT, selected, {}, url=lambda e: pages.get(e["id"]), venue=sp.venue)


def test_only_productions_listed_on_the_site():
    events = _scraped()
    titles = {e.title for e in events}
    assert {"NERO", "Memoriam", "Brixton Calling", "The Radium Girls"} <= titles
    assert not any("Black Writers Collective" in t for t in titles)
    assert all(e.source_url.startswith("https://southwarkplayhouse.co.uk/productions/") for e in events)
    assert len({e.external_id for e in events}) == len(events)


def test_buildings_split_by_seating_plan():
    by_title = {e.title: e.venue_slug for e in _scraped()}
    assert by_title["NERO"] == "southwark-playhouse-elephant"
    assert by_title["Private Jones"] == "southwark-playhouse-elephant"
    assert by_title["Memoriam"] == "southwark-playhouse-borough"
    assert by_title["Dog Mom"] == "southwark-playhouse-borough"
    assert sp.venue({}, {"venue": {"name": "Somewhere Else"}}) is None
