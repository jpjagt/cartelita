import datetime as dt
from pathlib import Path

from cartelera.scrapers.toffler import CLUB_URL, parse_club

FIXTURE = Path(__file__).parent / "fixtures" / "toffler_club.html"
TODAY = dt.date(2026, 10, 14)


def _events():
    return parse_club(FIXTURE.read_text(), TODAY)


def test_parses_one_club_night_per_date():
    events = _events()
    assert len(events) >= 6
    dates = [e.start_date for e in events]
    assert dates == sorted(dates) and len(set(dates)) == len(dates)
    for e in events:
        assert e.title.startswith("TOFFLER Presents")
        assert e.category_slugs == ["club"]
        assert e.source_url == CLUB_URL
        assert e.description and e.description.startswith("Line-up: ")
        assert e.start_time is None and e.price is None  # not stated per night


def test_dates_get_the_right_year():
    first = _events()[0]
    assert first.start_date == dt.date(2026, 10, 16)
    # A January date seen in December belongs to next year.
    html = FIXTURE.read_text().replace("Friday 16.10", "Friday 15.01")
    jan = [e for e in parse_club(html, dt.date(2026, 12, 20)) if e.start_date.month == 1]
    assert jan and jan[0].start_date.year == 2027


def test_external_ids_unique():
    ids = [e.external_id for e in _events()]
    assert len(ids) == len(set(ids))
