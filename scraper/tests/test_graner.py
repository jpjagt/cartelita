import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.graner import parse_agenda, _guess_year

FIXTURES = Path(__file__).parent / "fixtures"
CA_HTML = (FIXTURES / "graner_home_ca.html").read_text()
EN_HTML = (FIXTURES / "graner_home_en.html").read_text()

# Fixture captured 2026-06-09; pin "today" so year inference is deterministic.
TODAY = dt.date(2026, 6, 9)


@pytest.fixture
def events():
    return parse_agenda(CA_HTML, EN_HTML, today=TODAY)


def test_parses_events(events):
    assert len(events) >= 1


def test_valid_core_fields(events):
    for e in events:
        assert e.title and e.title.strip()
        assert isinstance(e.start_date, dt.date)
        assert e.source_url.startswith("http")
        assert e.category_slugs == ["dance"]


def test_known_category(events):
    for e in events:
        for c in e.category_slugs:
            assert c == "dance"


def test_external_id_unique_per_occurrence(events):
    ids = [e.external_id for e in events]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_external_id_includes_date(events):
    for e in events:
        assert e.start_date.isoformat() in e.external_id


def test_dates_are_current_month(events):
    # The homepage agenda is the current-month "June schedule" for the fixture.
    for e in events:
        assert e.start_date.month == 6
        assert e.start_date.year == 2026


def test_no_placeholder_event(events):
    # The decoy agenda template renders "titol" / 2-2-2023; ensure we did not
    # parse that stub.
    for e in events:
        assert e.title.lower() != "titol"
        assert e.start_date != dt.date(2023, 2, 2)


def test_known_real_event_present(events):
    # MUR MUR I ZO at Museu Tapies on 10 June 2026 is a real fixture event.
    match = [e for e in events if "MUR MUR" in e.title.upper()]
    assert match, "expected the MUR MUR I ZO presentation"
    e = match[0]
    assert e.start_date == dt.date(2026, 6, 10)
    assert e.source_url.startswith("https://granerbcn.cat/")


def test_english_translation_attached(events):
    # Internal granerbcn events should carry a ca->en title translation.
    match = [e for e in events if "MUR MUR" in e.title.upper()]
    e = match[0]
    en = [t for t in e.translations if t.lang == "en"]
    assert en, "expected an English translation"
    assert "MUR MUR" in en[0].title.upper()


def test_year_inference():
    # Month earlier than current -> next year; same/future -> current year.
    today = dt.date(2026, 6, 9)
    assert _guess_year(6, today=today) == 2026
    assert _guess_year(7, today=today) == 2026
    assert _guess_year(1, today=today) == 2027


def test_price_unknown_is_none(events):
    # Price is not published on the site; it must be left unknown (None),
    # never fabricated.
    for e in events:
        assert e.price is None
