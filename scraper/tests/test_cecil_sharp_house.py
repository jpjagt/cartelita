"""Cecil Sharp House (EFDSS) on the shared Spektrix helper joined to the
efdss.org what's-on listing, against saved responses (captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import cecil_sharp_house as csh

FIXTURES = Path(__file__).parent / "fixtures"


def _scraped():
    events = json.loads((FIXTURES / "cecil_sharp_house_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "cecil_sharp_house_spektrix_instances.json").read_text())
    by_plan = json.loads((FIXTURES / "cecil_sharp_house_spektrix_plan_venues.json").read_text())
    items = csh.parse_listing((FIXTURES / "cecil_sharp_house_site_listing.html").read_text())
    programme = csh.Programme(items)
    programme.prepare(events, instances)
    for inst in instances:
        inst["venue"] = by_plan.get(inst.get("planId"), {})
    selected = spk.select(events, instances, programme.categorize, csh.venue)
    return spk.build(csh.CLIENT, selected, {}, title=programme.title, url=programme.url, venue=csh.venue)


def test_gigs_and_dances_are_folk():
    scraped = _scraped()
    titles = {e.title for e in scraped}
    # Gigs, ceilidhs and barn dances — incl. those the box office leaves
    # unlabelled (Bhangra Ceilidh) — with the website's titles.
    assert {"The Furrow Collective", "Goblin Band", "Queer Ceilidh Dance Party",
            "Family Barn Dance", "Bhangra Ceilidh"} <= titles
    assert all(e.category_slugs == ["folk"] for e in scraped)
    assert {e.venue_slug for e in scraped} == {"cecil-sharp-house"}
    assert len({e.external_id for e in scraped}) == len(scraped)


def test_classes_talks_and_off_site_dropped():
    joined = " | ".join(e.title for e in _scraped())
    # Morris Dancing is "Dance" in the box office, a class on the website.
    for dropped in ("Morris Dancing", "English Country Dancing", "Intangible Cultural Heritage",
                    "A Dance Through History", "Inclusive Music Making"):
        assert dropped not in joined


def test_events_link_to_efdss_pages():
    furrow = next(e for e in _scraped() if e.title == "The Furrow Collective")
    assert furrow.source_url == "https://www.efdss.org/whats-on/26-gigs/16003-the-furrow-collective-2026"


def test_listing_parse_and_join_by_instance_id():
    items = csh.parse_listing((FIXTURES / "cecil_sharp_house_site_listing.html").read_text())
    by_cms, by_instance = csh.site_index(items)
    assert by_cms["16003"]["catid"] == 26
    assert by_instance["162801"]["id"] == 16003
    assert "Sharp's Folk Club" in {i["title"].strip() for i in items}
    event = {"id": "999AXX", "name": "Bhangra Ceilidh 2026"}
    inst = {"id": "160401AXYZ", "event": {"id": "999AXX"}}
    assert csh.join([event], [inst], items)["999AXX"]["catid"] == 27
