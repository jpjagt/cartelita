import datetime as dt
from pathlib import Path

from cartelera.scrapers.jamboree import parse_agenda

FIXTURE = Path(__file__).parent / "fixtures" / "jamboree_agenda.html"


def test_parses_at_least_one_event():
    html = FIXTURE.read_text()
    events = parse_agenda(html)
    assert len(events) >= 1


def test_events_are_jazz_categorized_with_dates():
    html = FIXTURE.read_text()
    events = parse_agenda(html)
    for ev in events:
        assert ev.category_slugs == ["jazz"]
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("http")


def test_parses_many_events():
    """JSON-LD blob contains 244 events in the saved fixture."""
    html = FIXTURE.read_text()
    events = parse_agenda(html)
    assert len(events) >= 50


def test_jam_session_present_with_time():
    html = FIXTURE.read_text()
    events = parse_agenda(html)
    jams = [e for e in events if "jam session" in e.title.lower()]
    assert jams, "expected at least one Jam Session in the fixture"
    j = jams[0]
    assert isinstance(j.start_date, dt.date)
    assert j.start_time is not None  # the jam has a real time, not the all-day sentinel
    assert j.recurrence_hint == "every Monday"


def test_events_have_source_urls():
    html = FIXTURE.read_text()
    events = parse_agenda(html)
    for ev in events:
        assert ev.source_url.startswith("https://jamboreejazz.com/")


def test_most_events_have_external_ids():
    html = FIXTURE.read_text()
    events = parse_agenda(html)
    with_id = [e for e in events if e.external_id]
    assert len(with_id) >= len(events) * 0.9


def test_jam_session_has_recurrence_hint():
    html = FIXTURE.read_text()
    events = parse_agenda(html)
    jams = [e for e in events if "jam" in e.title.lower()]
    if jams:
        assert jams[0].recurrence_hint is not None


def test_all_day_sentinel_events_have_no_time():
    html = FIXTURE.read_text()
    events = parse_agenda(html)
    # Events using the 00:00–23:59:59 all-day sentinel should report no time.
    # We can't see raw json here, but we can assert no event has end_time exactly 23:59:59.
    assert all(e.end_time != dt.time(23, 59, 59) for e in events)
    # And at least some events legitimately have a real start_time.
    assert any(e.start_time is not None for e in events)
