import datetime as dt
from pathlib import Path

from cartelera.scrapers.jamboree import parse_agenda

FIXTURE = Path(__file__).parent / "fixtures" / "jamboree_agenda.html"


def test_parses_at_least_one_event():
    html = FIXTURE.read_text()
    events = parse_agenda(html, today=dt.date(2026, 6, 1))
    assert len(events) >= 1


def test_events_are_jazz_categorized_with_dates():
    html = FIXTURE.read_text()
    events = parse_agenda(html, today=dt.date(2026, 6, 1))
    for ev in events:
        assert ev.category_slugs == ["jazz"]
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("http")


def test_parses_many_events():
    """JSON-LD blob contains 244 events in the saved fixture."""
    html = FIXTURE.read_text()
    events = parse_agenda(html, today=dt.date(2026, 6, 1))
    assert len(events) >= 50


def test_first_event_is_jam_session():
    """The fixture opens with the Monday Jam Session on 2026-06-01."""
    html = FIXTURE.read_text()
    events = parse_agenda(html, today=dt.date(2026, 6, 1))
    first = events[0]
    assert "Jam Session" in first.title
    assert first.start_date == dt.date(2026, 6, 1)
    assert first.start_time == dt.time(19, 0)


def test_events_have_source_urls_and_external_ids():
    html = FIXTURE.read_text()
    events = parse_agenda(html, today=dt.date(2026, 6, 1))
    for ev in events:
        assert ev.source_url.startswith("https://jamboreejazz.com/")
        # external_id is the URL slug, always present for these events
        assert ev.external_id is not None


def test_jam_session_has_recurrence_hint():
    html = FIXTURE.read_text()
    events = parse_agenda(html, today=dt.date(2026, 6, 1))
    jams = [e for e in events if "jam" in e.title.lower()]
    if jams:
        assert jams[0].recurrence_hint is not None
