"""Green Note from its Theater-for-WordPress listing (+ production pages for
the start time), against saved, trimmed pages (captured 2026-10-25)."""

import datetime as dt
from pathlib import Path

from cartelera.scrapers import green_note as gn

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 25)


def _rows():
    return gn.parse_listing((FIXTURES / "green_note_listing.html").read_text(), TODAY)


def _events():
    times = {"https://www.greennote.co.uk/production/anna-massie/": gn.production_times(
        (FIXTURES / "green_note_production_anna-massie.html").read_text(), TODAY)}
    return gn.parse(_rows(), times, TODAY)


def test_only_green_notes_own_rooms():
    rows = _rows()
    events = _events()
    assert len(rows) == 174
    own = [r for r in rows if r["room"] in gn.ROOMS and "cancel" not in r["status"].lower()]
    assert len(events) == len(own) > 140
    titles = {e.title for e in events}
    assert "Green Note Presents: Rob Quo + Dill Chatter" not in titles  # The Water Rats
    assert "The Folly Brothers" not in titles  # cancelled, no room
    assert all(e.category_slugs == ["folk"] for e in events)
    assert any(e.annotations == ["Basement Bar"] for e in events)


def test_year_from_weekday_and_unique_ids():
    events = _events()
    assert all(e.start_date >= TODAY for e in events)
    assert max(e.start_date for e in events).year == 2027
    assert len({e.external_id for e in events}) == len(events)
    assert sum(1 for e in events if e.price) / len(events) >= 0.95


def test_fields_of_one_event():
    massie = next(e for e in _events() if e.title == "Anna Massie")
    assert massie.start_date == dt.date(2026, 10, 27)
    assert massie.start_time == dt.time(19, 0)  # from its production page
    assert massie.price == "£15"
    assert massie.source_url == "https://www.greennote.co.uk/production/anna-massie/"
    assert massie.external_id == "anna-massie@2026-10-27"


def test_price_and_status():
    row = {"price": "£\xa012.50", "status": ""}
    assert gn._price(row) == "£12.50"
    assert gn._price({"price": "£ 12.00", "status": "wp_theatre_event_tickets_status_soldout Sold out"}) == "sold-out"
    assert gn._price({"price": "", "status": ""}) is None
