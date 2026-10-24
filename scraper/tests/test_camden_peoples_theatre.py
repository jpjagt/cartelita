"""Camden People's Theatre on the shared Spektrix helper, against saved API
responses and show-page ids (captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import camden_peoples_theatre as cpt

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / f"camden_peoples_theatre_spektrix_{name}.json").read_text())


def _scraped():
    events, instances = _load("events"), _load("instances")
    by_plan = _load("plan_venues")
    for inst in instances:
        inst["venue"] = by_plan.get(inst.get("planId"), {})
    pages = spk.site_urls({u: set(ids) for u, ids in _load("site_ids").items()}, events, instances)
    selected = spk.select(events, instances, cpt.categorize, cpt.venue)
    return spk.build(cpt.CLIENT, selected, {}, url=lambda e: pages.get(e["id"]), venue=cpt.venue)


def test_every_performance_in_the_building_kept():
    events = _scraped()
    raw = _load("events")
    assert {e.title for e in events} == {" ".join(r["name"].split()) for r in raw}
    assert all(e.venue_slug == "camden-peoples-theatre" for e in events)
    assert all(e.category_slugs == ["theater"] for e in events)
    assert len({e.external_id for e in events}) == len(events)


def test_partner_and_online_venues_dropped():
    assert cpt.venue({}, {"venue": {"name": "Online"}}) is None
    assert cpt.venue({}, {"venue": {"name": "Soho Theatre"}}) is None


def test_show_pages_joined_by_ticket_links():
    assert spk.embedded_ids("<button onclick=\"location.href='https://cptheatre.co.uk/tickets/351844'\">") == {"351844"}
    by_title = {e.title: e.source_url for e in _scraped()}
    assert by_title["Sharp Edges"] == "https://cptheatre.co.uk/whatson/Sharp-Edges"
    # Sold out / off sale: no ticket links on its page → Spektrix event page.
    assert by_title["Trash Salad"].startswith("https://tickets.cptheatre.co.uk/camdenpeoplestheatre/website/")
