"""The Place on the shared Spektrix helper, against saved API responses
(events + ~2 weeks of instances plus a few later ones, captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import the_place

FIXTURES = Path(__file__).parent / "fixtures"


def _load():
    events = json.loads((FIXTURES / "the_place_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "the_place_spektrix_instances.json").read_text())
    return events, instances


def _scraped():
    events, instances = _load()
    selected = spk.select(events, instances, the_place.categorize)
    return spk.build(the_place.CLIENT, selected, {}, title=the_place.title)


def test_keeps_performances_only():
    events = _scraped()
    titles = {e.title for e in events}
    assert {"Marikiscrycrycry - Hang Time", "Ekleido - Femina", "Jo Bannon - The Dirty Work",
            "Starchitects Save Santa", "LCDS: Mixed Bill 2027"} <= titles
    joined = " | ".join(titles)
    # Classes, touch tours, Resolution workshops, open/experience days, hires.
    for dropped in ("TOUCH TOUR", "Drop in", "Professional Class", "RES27", "Open Day",
                    "Experience Day", "ZooNation", "Butoh Intensive", "Info Session"):
        assert dropped not in joined
    assert len({e.external_id for e in events}) == len(events)


def test_family_programme_is_also_kids():
    by_title = {e.title: e.category_slugs for e in _scraped()}
    assert by_title["Starchitects Save Santa"] == ["dance", "kids"]
    assert by_title["Marikiscrycrycry - Hang Time"] == ["dance"]
    assert any(t.startswith("Res 27:") and c == ["dance"] for t, c in by_title.items())


def test_season_prefix_stripped_from_titles():
    assert the_place.title({"name": "Autumn/ Winter 26: Ekleido - Femina"}) == "Ekleido - Femina"
    assert the_place.title({"name": "Spring/Summer 2027: Lost Dog - Juliet & Romeo"}) == "Lost Dog - Juliet & Romeo"
    assert the_place.title({"name": "Autumn/Winter 2026: The Peter Farley  Project"}) == "The Peter Farley Project"
    assert all(not e.title.startswith(("Autumn", "Spring")) for e in _scraped())


def test_off_site_and_type_labels():
    base = {"attribute_WebsiteListing": "Performance", "attribute_WebsiteVenue": "at The Place",
            "attribute_Type": "Theatre Programme - 99A 8054"}
    assert the_place.categorize(base) == ["dance"]
    assert the_place.categorize({**base, "attribute_WebsiteVenue": "off-site"}) == []
    assert the_place.categorize({**base, "attribute_Type": "Resolution Workshops –1420 10B"}) == []
    assert the_place.categorize({**base, "attribute_Type": "Resolution 99A 8054"}) == ["dance"]
    assert the_place.categorize({**base, "attribute_TicketName1": "TOUCH TOUR"}) == []


def test_show_page_join_on_book_instance_links():
    events, instances = _load()
    page = "<a href='https://theplace.org.uk/book/instance/882636'>Book</a>"
    ids = set(the_place._BOOK_INSTANCE.findall(page))
    url = "https://theplace.org.uk/events/autumn-winter-26-hang-time"
    pages = spk.site_urls({url: ids}, events, instances)
    hang_time = next(e for e in events if "Hang Time" in e["name"])
    assert pages == {hang_time["id"]: url}


def test_price_from_standard_band_only():
    price_list = {"prices": [
        {"amount": 22.0, "isBandDefault": True, "priceBand": {"name": "Standard "}},
        {"amount": 5.0, "isBandDefault": True, "priceBand": {"name": "LCDS Student"}},
        {"amount": 18.0, "isBandDefault": True, "priceBand": {"name": "Wheelchair spaces"}},
        {"amount": 18.0, "isBandDefault": False, "priceBand": {"name": "Standard "}},
    ]}
    assert the_place.price_text(price_list) == "£22"
    no_standard = {"prices": [{"amount": 10.0, "isBandDefault": True, "priceBand": {"name": "Stalls"}}]}
    assert the_place.price_text(no_standard) == "£10"
