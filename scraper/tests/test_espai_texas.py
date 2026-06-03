from __future__ import annotations
import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.espai_texas import parse_agenda

FIXTURE = Path(__file__).parent / "fixtures" / "espai_texas_agenda.html"


@pytest.fixture(scope="module")
def events():
    return parse_agenda(FIXTURE.read_text(encoding="utf-8"))


def test_parses_many_events(events):
    # The homepage calendar lists every cinema session; expect a healthy batch.
    assert len(events) >= 10


def test_every_event_has_valid_core_fields(events):
    for ev in events:
        assert ev.title and ev.title.strip()
        assert isinstance(ev.start_date, dt.date)
        assert ev.source_url and ev.source_url.startswith("http")
        assert ev.category_slugs == ["film"]


def test_only_cinema_category(events):
    # Theatre (espectacle) and activitat anchors must be excluded.
    assert all(ev.category_slugs == ["film"] for ev in events)


def test_no_theatre_or_activity_titles_leak(events):
    # These appear in the fixture's calendar but are espectacle/activitat, not
    # pelicula — they must not be present among scraped (film) events.
    titles = {ev.title.upper() for ev in events}
    assert "PERMAGEL" not in titles
    assert "UNA ANIQUILACIÓ FALLIDA" not in titles


def test_time_present_for_most_and_midnight_is_none(events):
    # "00:00" placeholder sessions map to unknown time (None); the rest have a time.
    with_time = [ev for ev in events if ev.start_time is not None]
    assert len(with_time) / len(events) >= 0.7
    for ev in with_time:
        assert ev.start_time != dt.time(0, 0)


def test_price_coverage_and_day_of_week_rule(events):
    # Every session gets a price from the published day-of-week rule.
    assert all(ev.price for ev in events)
    for ev in events:
        wd = ev.start_date.weekday()
        if wd == 3:
            assert ev.price == "4€"  # Thursday: dia de l'espectador
        elif wd >= 5:
            assert ev.price == "8€"  # weekend
        else:
            assert ev.price == "6€"  # Mon–Fri


def test_external_id_unique_per_occurrence(events):
    # The upsert dedups on (venue, external_id) and raises on in-batch dupes;
    # ids must be unique per occurrence (a film screens on many dates/times).
    ids = [ev.external_id for ev in events]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_external_id_qualified_by_date_and_time(events):
    # A coarse film slug would collapse occurrences; ids carry date+time.
    for ev in events:
        assert "@" in ev.external_id
        assert ev.start_date.isoformat() in ev.external_id


def test_recurring_film_appears_on_multiple_dates(events):
    # Sanity: at least one film screens across multiple dates (occurrence dedup
    # must keep them all, not collapse to one).
    from collections import Counter

    by_title = Counter(ev.title for ev in events)
    assert max(by_title.values()) >= 2
