import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.arten import parse_afisha

FIXTURES = Path(__file__).parent / "fixtures"
HY_HTML = (FIXTURES / "arten_afisha_hy.html").read_text()
RU_HTML = (FIXTURES / "arten_afisha_ru.html").read_text()
EN_HTML = (FIXTURES / "arten_afisha_en.html").read_text()

# Fixture captured 2026-08-18; pin "today" so the past-date filter is
# deterministic.
TODAY = dt.date(2026, 8, 18)


@pytest.fixture
def events():
    return parse_afisha(HY_HTML, RU_HTML, EN_HTML, today=TODAY)


def test_parses_events(events):
    assert len(events) >= 5


def test_valid_core_fields(events):
    for e in events:
        assert e.title and e.title.strip()
        assert isinstance(e.start_date, dt.date)
        assert e.start_date >= TODAY
        assert e.source_url.startswith("https://www.arten.theater/hy/")
        assert e.category_slugs == ["theater"]


def test_external_id_unique_per_occurrence(events):
    ids = [e.external_id for e in events]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_external_id_includes_date(events):
    # Occurrence keys embed the date; this is what keeps the recurring
    # project (same title, same source_url) from collapsing in the upsert.
    for e in events:
        assert e.start_date.isoformat() in e.external_id


def test_time_coverage(events):
    # Every card on the afisha carries a start time.
    assert all(e.start_time is not None for e in events)


def test_end_time_when_range(events):
    # The recurring project cards show a 14:30–16:00 range.
    ranged = [e for e in events if e.end_time is not None]
    assert ranged
    for e in ranged:
        assert e.end_time > e.start_time


def test_price_coverage(events):
    # Every card on the afisha shows a price; ֏ is normalized to AMD.
    priced = [e for e in events if e.price]
    assert len(priced) == len(events)
    for e in priced:
        assert e.price in ("free", "sold-out") or "AMD" in e.price
        assert "֏" not in e.price


def test_specific_performance(events):
    # Find by predicate, not position (fixture order is volatile).
    matches = [e for e in events if "osen-patriarha" in (e.external_id or "")]
    assert matches
    e = matches[0]
    assert e.start_date == dt.date(2026, 8, 23)
    assert e.start_time == dt.time(19, 0)
    assert e.price == "5000 AMD"
    assert e.source_url == "https://www.arten.theater/hy/performances/osen-patriarha"
    assert e.image_url and e.image_url.startswith("https://")


def test_translations_ru_en(events):
    # All three site languages carry every card; translations zip by key.
    for e in events:
        langs = {t.lang for t in e.translations}
        assert langs == {"ru", "en"}
        for t in e.translations:
            assert t.title and t.title != e.title
            assert t.source_url and f"/{t.lang}/" in t.source_url


def test_language_never_inferred(events):
    # The site states no per-event performance language anywhere.
    assert all(e.language is None for e in events)


def test_past_events_filtered():
    events = parse_afisha(HY_HTML, RU_HTML, EN_HTML, today=dt.date(2026, 9, 1))
    assert events
    for e in events:
        assert e.start_date >= dt.date(2026, 9, 1)


def test_annotations_no_category_leak(events):
    for e in events:
        assert "theater" not in e.annotations
