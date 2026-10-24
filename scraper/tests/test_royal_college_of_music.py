"""Royal College of Music on the shared Spektrix helper, against saved API
responses (captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import royal_college_of_music as rcm

FIXTURES = Path(__file__).parent / "fixtures"


def _scraped(prices=None):
    events = json.loads((FIXTURES / "royal_college_of_music_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "royal_college_of_music_spektrix_instances.json").read_text())
    by_plan = json.loads((FIXTURES / "royal_college_of_music_spektrix_plan_venues.json").read_text())
    for inst in instances:
        inst["venue"] = by_plan.get(inst.get("planId"), {})
    return rcm.build(spk.select(events, instances, rcm.categorize, rcm.venue), prices or {})


def test_concerts_and_opera_only():
    scraped = _scraped()
    titles = {e.title for e in scraped}
    assert {"The Firebird", "Chamber Tuesdays", "Opera Double Bill: Debussy & Ravel"} <= titles
    joined = " | ".join(titles)
    for dropped in ("Museum", "Tour", "Masterclass", "RCMJD", "Explorers Course", "RCM Insights",
                    "Ceilidh", "GALSI"):
        assert dropped not in joined
    assert all(e.category_slugs == ["classical"] for e in scraped)
    assert {e.venue_slug for e in scraped} == {"royal-college-of-music"}
    assert len({e.external_id for e in scraped}) == len(scraped)


def test_performance_page_and_pwyc_price():
    events = _scraped({})
    firebird = [e for e in events if e.title == "The Firebird"]
    assert len(firebird) == 2
    assert len({e.source_url for e in firebird}) == 2  # one page per performance
    assert all(e.source_url.startswith("https://www.rcm.ac.uk/events/details/?id=") for e in firebird)
    tuesdays = next(e for e in events if e.title == "Chamber Tuesdays")
    assert tuesdays.price == "pay what you can"
    assert firebird[0].price is None  # no price list fetched offline; not PWYC


def test_off_site_venue_dropped():
    assert rcm.venue({}, {"venue": {"name": "Imperial College", "address": ""}}) is None
    assert rcm.venue({}, {"venue": {"name": "Britten Theatre",
                                    "address": "Royal College of Music, Prince Consort Road, London, SW7 2BS"}}) \
        == "royal-college-of-music"
