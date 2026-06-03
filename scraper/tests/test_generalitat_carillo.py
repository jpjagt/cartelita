import datetime as dt
from pathlib import Path

from cartelera.scrapers.generalitat_carillo import (
    parse_agenda,
    _infer_year,
    _parse_time,
    VENUE_SLUG,
)

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA = FIXTURES / "generalitat_carillo_agenda.html"

# The fixture lists concrete dates (June/July 2026); pin "today" so the
# year-inference and the upcoming-date set are deterministic.
TODAY = dt.date(2026, 6, 2)


def _events():
    return parse_agenda(AGENDA.read_text(), today=TODAY)


def test_parses_several_concerts():
    # 2 monthly "Pròxims concerts" + 6 festival concerts in the fixture.
    events = _events()
    assert len(events) >= 6


def test_events_have_dates_titles_urls():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url == "https://presidencia.gencat.cat/ca/carillo"


def test_every_concert_is_classical():
    assert all(ev.category_slugs == ["classical"] for ev in _events())


def test_all_concerts_are_free():
    # Carillon concerts are always free admission -> price must normalize to "free".
    events = _events()
    assert events
    assert all(ev.price == "free" for ev in events)


def test_every_event_has_a_start_time():
    # Monthly concerts default to the midday slot; the festival lists 21:00.
    for ev in _events():
        assert ev.start_time is not None


def test_festival_concerts_at_21h():
    festival = [e for e in _events() if e.external_id and "festival" in e.external_id]
    assert len(festival) == 6, "expected the 6 festival dates from the fixture"
    for ev in festival:
        assert ev.start_time == dt.time(21, 0)
        assert ev.start_date.month == 7
        assert ev.start_date.year == 2026
        assert "Festival Internacional de Caril" in ev.title


def test_monthly_concerts_at_midday():
    monthly = [
        e for e in _events() if e.external_id and "festival" not in e.external_id
    ]
    assert monthly, "expected monthly concerts from the fixture"
    for ev in monthly:
        assert ev.start_time == dt.time(12, 0)


def test_known_dates_present():
    dates = {e.start_date for e in _events()}
    # Monthly upcoming concerts + the six festival dates.
    assert dt.date(2026, 6, 7) in dates
    assert dt.date(2026, 7, 5) in dates
    for d in (17, 18, 19, 24, 25, 26):
        assert dt.date(2026, 7, d) in dates


def test_external_ids_unique_per_occurrence():
    ids = [e.external_id for e in _events()]
    assert all(ids), "every event must carry an external_id"
    assert len(ids) == len(set(ids)), "external_ids must be unique per occurrence"
    assert all(i.startswith(VENUE_SLUG) for i in ids)


def test_annotations_capture_programme_without_category_leak():
    events = _events()
    annotated = [e for e in events if e.annotations]
    assert annotated, "expected programme/edition annotations"
    for ev in events:
        assert "classical" not in ev.annotations


def test_festival_titles_carry_programme_name():
    festival = [e for e in _events() if e.external_id and "festival" in e.external_id]
    # e.g. "...: Música catalana", "...: A la festa!"
    assert any("Música catalana" in e.title for e in festival)
    assert any("Beatles" in e.title for e in _events())  # monthly July concert


def test_infer_year_rolls_forward():
    # January seen in December must roll to the next year.
    assert _infer_year(1, dt.date(2026, 12, 15)) == 2027
    assert _infer_year(6, dt.date(2026, 6, 2)) == 2026
    assert _infer_year(7, dt.date(2026, 6, 2)) == 2026


def test_parse_time_variants():
    assert _parse_time("a les 12h") == dt.time(12, 0)
    assert _parse_time("a les 12 h") == dt.time(12, 0)
    assert _parse_time("Hora: 21:00 h.") == dt.time(21, 0)
    assert _parse_time("no clock here", default=dt.time(12, 0)) == dt.time(12, 0)
    assert _parse_time("no clock here") is None
