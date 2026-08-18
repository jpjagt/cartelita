import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers.ulikhanyan_club import (
    parse_agenda,
    parse_ticket_ids,
    parse_token,
    price_from_ticket,
    _resolve_date,
)

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA = FIXTURES / "ulikhanyan_club_agenda.html"
# The fixture was captured on this date; the site's dates carry no year.
TODAY = dt.date(2026, 8, 18)


def _events():
    return parse_agenda(AGENDA.read_text(), today=TODAY)


def test_parses_all_events():
    assert len(_events()) == 8  # one concert per night, Aug 18-25


def test_events_have_core_fields():
    for ev in _events():
        assert ev.title
        assert isinstance(ev.start_date, dt.date)
        assert ev.source_url.startswith("https://ulikhanyanclub.com/en/buy-ticket/")
        assert ev.category_slugs == ["jazz"]
        assert ev.external_id and ev.external_id.isdigit()
        assert ev.description
        assert ev.image_url and ev.image_url.startswith("https://api.haytoms.am/upload/")
        # Instrumental jazz: the source states no language.
        assert ev.language is None


def test_external_ids_unique_per_occurrence():
    ids = [e.external_id for e in _events()]
    assert len(ids) == len(set(ids))


def test_armenian_dates_resolved():
    # `.event-fee2` is "18  Օգոստոս  Երեքշաբթի 20:30" (Armenian month, no year).
    events = _events()
    silence = next(e for e in events if e.title == "Silence Duo")
    assert silence.start_date == dt.date(2026, 8, 18)
    assert silence.start_time == dt.time(20, 30)
    manuk = next(e for e in events if "Manuk Ghazaryan" in e.title)
    assert manuk.start_date == dt.date(2026, 8, 25)


def test_all_events_have_showtime():
    for ev in _events():
        assert ev.start_time == dt.time(20, 30)


def test_dates_form_consecutive_nightly_run():
    # The agenda is one concert per night over a rolling week; a gap or
    # duplicate date would mean date parsing (or year inference) broke.
    dates = sorted(e.start_date for e in _events())
    assert dates[0] == TODAY
    assert all((b - a).days == 1 for a, b in zip(dates, dates[1:]))


def test_year_rollover_resolution():
    # New Year's Eve window: a January date seen in late December is next year.
    assert _resolve_date(1, "Հունվար", dt.date(2026, 12, 28)) == dt.date(2027, 1, 1)
    assert _resolve_date(31, "Դեկտեմբեր", dt.date(2027, 1, 2)) == dt.date(2026, 12, 31)
    assert _resolve_date(18, "Օգոստոս", TODAY) == dt.date(2026, 8, 18)


def test_jam_session_recurrence_hint():
    jam = next(e for e in _events() if "JAM SESSION" in e.title)
    assert jam.recurrence_hint == "every Monday"
    others = [e for e in _events() if "JAM SESSION" not in e.title]
    assert all(e.recurrence_hint is None for e in others)


def test_ticket_ids_map_events_to_haytoms_widget():
    ids = parse_ticket_ids(AGENDA.read_text())
    assert ids["3041"] == "13940"
    assert ids["3047"] == "13946"
    assert set(ids) == {e.external_id for e in _events()}


def test_token_extracted():
    token = parse_token(AGENDA.read_text())
    assert token and token.startswith("eyJ")  # a JWT


def test_price_from_seat_map_fixtures():
    # Flat 5000 AMD night and the 3000 AMD Monday jam session.
    regular = json.loads((FIXTURES / "ulikhanyan_club_ticket_13940.json").read_text())
    assert price_from_ticket(regular) == "5000 AMD"
    jam = json.loads((FIXTURES / "ulikhanyan_club_ticket_13946.json").read_text())
    assert price_from_ticket(jam) == "3000 AMD"


def _payload(places):
    return {"map": {"Levels": [{"Places": places}]}}


def test_price_convention_edge_cases():
    # No active seats left => sold-out.
    sold = _payload([{"Price": 5000, "active": False}, {"Price": 5000, "active": False}])
    assert price_from_ticket(sold) == "sold-out"
    # All zero-priced => free.
    free = _payload([{"Price": 0, "active": True}])
    assert price_from_ticket(free) == "free"
    # Minor tier spread (hi < 2*lo) collapses to the highest public price.
    minor = _payload([{"Price": 5000, "active": True}, {"Price": 7000, "active": True}])
    assert price_from_ticket(minor) == "7000 AMD"
    # Meaningful spread (hi >= 2*lo) keeps the range.
    wide = _payload([{"Price": 3000, "active": True}, {"Price": 8000, "active": True}])
    assert price_from_ticket(wide) == "3000–8000 AMD"
    # No seat map at all => unknown.
    assert price_from_ticket({"map": None}) is None
    assert price_from_ticket({}) is None
