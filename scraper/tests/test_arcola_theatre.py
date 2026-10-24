"""Arcola Theatre on the shared Spektrix helper, against saved API responses
(captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import arcola_theatre as arcola

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / f"arcola_theatre_spektrix_{name}.json").read_text())


def _scraped():
    events, instances = _load("events"), _load("instances")
    by_plan = _load("plan_venues")
    for inst in instances:
        inst["venue"] = by_plan.get(inst.get("planId"), {})
    pages = spk.site_urls({u: set(ids) for u, ids in _load("site_ids").items()}, events, instances)
    selected = spk.select(events, instances, arcola.categorize, arcola.venue)
    return spk.build(arcola.CLIENT, selected, {}, title=arcola.title,
                     url=lambda e: pages.get(e["id"]), venue=arcola.venue)


def test_stage_shows_kept_participation_dropped():
    events = _scraped()
    titles = {e.title for e in events}
    assert {"The Master Builder", "The Ugly One", "Incident at Vichy"} <= titles
    # Arcola Youth Theatre terms sit on the "Workshops" venue (one is even
    # coded Genre=Theatre): dropped.
    assert not any("AYT" in t for t in titles)
    assert all(e.venue_slug == "arcola-theatre" for e in events)
    assert all(e.category_slugs == ["theater"] for e in events)
    assert len({e.external_id for e in events}) == len(events)


def test_season_prefix_stripped_and_site_pages_joined():
    events = _scraped()
    assert not any(e.title[:4].isdigit() for e in events)
    by_title = {e.title: e.source_url for e in events}
    assert by_title["The Master Builder"] == "https://www.arcolatheatre.com/event/the-master-builder/"


def test_grimeborn_is_classical_workshops_dropped():
    grimeborn = {"attribute_Genre": "Theatre", "attribute_Festival": "Grimeborn"}
    assert arcola.categorize(grimeborn) == ["classical"]
    assert arcola.categorize({"attribute_Genre": "Workshop"}) == []
    assert arcola.title({"name": "2027: The Reckoning "}) == "The Reckoning"
    assert arcola.venue({}, {"venue": {"name": "Workshops"}}) is None
