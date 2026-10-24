"""Unicorn Theatre on the shared Spektrix helper, against saved API responses
(captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import unicorn_theatre as uni

FIXTURES = Path(__file__).parent / "fixtures"


def _raw():
    events = json.loads((FIXTURES / "unicorn_theatre_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "unicorn_theatre_spektrix_instances.json").read_text())
    return events, instances


def _scraped():
    events, instances = _raw()
    return spk.build(uni.CLIENT, spk.select(events, instances, uni.categorize, uni.venue), {}, venue=uni.venue)


def test_public_performances_only():
    events, instances = _raw()
    scraped = _scraped()
    kept = {e.external_id for e in scraped}
    schools = [i for i in instances if i.get("attribute_Owner") == "Schools"]
    public = [i for i in instances if i.get("attribute_Owner") in ("Public", "Press Night")]
    assert schools and public
    assert not kept & {i["id"] for i in schools}
    assert {i["id"] for i in public if not i.get("cancelled")} == kept
    assert len(kept) == len(scraped)


def test_all_kids_one_venue_spektrix_page():
    scraped = _scraped()
    assert {e.title for e in scraped} >= {"Home Song", "Pocket Money"}
    assert all(e.category_slugs == ["kids"] for e in scraped)
    assert {e.venue_slug for e in scraped} == {"unicorn-theatre"}
    home = next(e for e in scraped if e.title == "Home Song")
    assert home.source_url.startswith("https://system.spektrix.com/unicorntheatre/website/EventDetails.aspx?EventId=")


def test_rules():
    assert uni.categorize({"attribute_EventType": "Unicorn Production "}) == ["kids"]
    assert uni.categorize({"attribute_EventType": "Visiting Company "}) == ["kids"]
    assert uni.categorize({}) == []
    press = {"attribute_Owner": "Press Night", "attribute_Location": "Unicorn Theatre (Weston)"}
    assert uni.venue({}, press) == "unicorn-theatre"
    assert uni.venue({}, {**press, "attribute_Owner": "Schools"}) is None
    assert uni.venue({}, {**press, "attribute_Location": "Digital theatre in your home"}) is None
