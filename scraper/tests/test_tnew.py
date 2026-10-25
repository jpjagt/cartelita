"""The shared TNEW helper, against a saved productionseasons payload
(Old Vic, captured 2026-10-25)."""

import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers import _tnew as tnew

FIXTURES = Path(__file__).parent / "fixtures"


def _perfs(name):
    return tnew.performances(json.loads((FIXTURES / name).read_text())["productions"])


def test_performances_are_flattened_in_local_time():
    perfs = _perfs("old_vic_tnew.json")
    assert perfs and perfs == sorted(perfs, key=lambda p: (p.start, p.production_id))
    first = perfs[0]
    assert first.production_title == "Martin Guerre"
    assert first.url.endswith(f"/{first.performance_id}")  # Old Vic: /<slug>/<perfId>
    assert first.start.tzinfo is None


def test_utc_performance_date_becomes_london_wall_time():
    # performanceDate is UTC; after the clocks go forward a 13:00 matinee
    # reads 12:00+00:00.
    prod = {"productionSeasonId": 1, "productionTitle": "<a href='x'>Show</a>", "performances": [
        {"id": 2, "performanceDate": "2027-03-28T12:00:00+00:00", "performanceStatusMessage": "<h2>SOLD OUT</h2>"},
        {"id": 3, "performanceDate": "2026-11-28T19:30:00+00:00", "productTypeName": "BSL Interpreted"},
        {"id": 4, "performanceDate": "2026-11-28T19:30:00+00:00"},  # same time, other seating product
    ]}
    perfs = tnew.performances([prod])
    assert [p.start for p in perfs] == [dt.datetime(2026, 11, 28, 19, 30), dt.datetime(2027, 3, 28, 13, 0)]
    assert perfs[1].sold_out and perfs[0].production_title == "Show"
    ev = tnew.event(perfs[0], title="Show", source_url="u", category_slugs=["theater"], price="£10")
    assert ev.annotations == ["BSL interpreted"] and ev.price == "£10" and ev.external_id == "3"
    assert tnew.event(perfs[1], title="Show", source_url="u", category_slugs=["theater"], price="£10").price == "sold-out"


def test_booking_ids_on_allowed_hosts_only():
    html = """<a href="https://my.x.com/63940/63941">a</a> <a href="https://events.x.com/events/95888">b</a>
              <a href="https://images.x.com/uploads/2026/08/pic.jpg">c</a> <a href="https://other.com/1234/5678">d</a>"""
    ids = tnew.booking_ids(html, ["my.x.com", "events.x.com"])
    assert ids.performances == {("63940", "63941")}
    assert ids.all_productions == {"63940", "95888"}


def test_price_helpers():
    assert tnew.ladder_price(["£25, £36, £51", "£20, £27, £105"]) == "£20–105"
    assert tnew.ladder_price(["£28/£35"]) == "£35"
    assert tnew.ladder_price(["no price"]) is None
    assert tnew.price_range([0, 0]) == "free"
