"""Islington Folk Club from its static programme table and home page
(captured 2026-10-25)."""

import datetime as dt
from pathlib import Path

from cartelera.scrapers import islington_folk_club as ifc

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 25)


def _read(name):
    return (FIXTURES / name).read_bytes().decode(ifc.ENCODING)


def _events(today=TODAY):
    time, price = ifc.club_facts(_read("islington_folk_club_home.html"))
    return ifc.parse(_read("islington_folk_club_programme.html"), today, time, price)


def test_club_facts_from_home_page():
    assert ifc.club_facts(_read("islington_folk_club_home.html")) == (dt.time(20, 0), "£10")


def test_one_folk_night_per_programme_row():
    events = _events()
    assert len(events) == 12
    assert all(e.category_slugs == ["folk"] for e in events)
    assert all(e.start_date.weekday() == 3 for e in events)  # Thursdays
    assert all(e.start_time == dt.time(20, 0) and e.price == "£10" for e in events)
    assert len({e.external_id for e in events}) == len(events)
    assert "Club closed" not in {e.title for e in events}


def test_fields_and_encoding():
    first = _events()[0]
    assert (first.start_date, first.title) == (dt.date(2026, 10, 29), "Louise and Chris Rogan")
    assert first.source_url == "https://www.islingtonfolkclub.co.uk/programme.html"
    moylan = next(e for e in _events() if e.title == "Linda Moylan")
    assert "London’s East End" in moylan.description  # windows-1252 apostrophe


def test_passed_nights_dropped():
    assert all(e.start_date >= dt.date(2027, 1, 1) for e in _events(dt.date(2027, 1, 1)))
