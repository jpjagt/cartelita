import datetime as dt
from pathlib import Path
from cartelera.scrapers.jamboree import parse_agenda

FIXTURE = Path(__file__).parent / "fixtures" / "jamboree_agenda.html"


def _events():
    return parse_agenda(FIXTURE.read_text())


def test_parses_many_events():
    events = _events()
    assert len(events) >= 50  # the list view holds the full agenda


def test_events_have_dates_titles_urls():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("https://jamboreejazz.com/")
        assert ev.category_slugs[0] in {"jazz", "club"}


def test_most_events_have_a_price():
    events = _events()
    with_price = [e for e in events if e.price]
    assert len(with_price) >= len(events) * 0.9  # price is on nearly every card


def test_club_events_detected_via_plus18_tag():
    events = _events()
    club = [e for e in events if e.category_slugs == ["club"]]
    jazz = [e for e in events if e.category_slugs == ["jazz"]]
    assert club, "expected at least one +18 club/disco event"
    assert jazz, "expected jazz concerts"
    # The recurring resident club nights ("... Night: DJ ...") are +18 -> club.
    resident = [e for e in events if "night:" in e.title.lower()]
    assert resident, "expected resident club nights in the fixture"
    assert all(e.category_slugs == ["club"] for e in resident)
    # A live act that merely mentions a DJ warm-up stays a jazz concert (it has a
    # genre tag, not +18) — categorization is tag-driven, not title-keyword-driven.


def test_genre_tags_captured_as_annotations_without_plus18():
    events = _events()
    annotated = [e for e in events if e.annotations]
    assert annotated, "expected genre annotations on some events"
    # The +18 discriminator must never leak into annotations.
    assert all("+18" not in e.annotations for e in events)


def test_jam_session_present_with_time_and_recurrence():
    events = _events()
    jams = [e for e in events if "jam session" in e.title.lower()]
    assert jams, "expected a Jam Session in the fixture"
    j = jams[0]
    assert j.start_time is not None
    assert j.recurrence_hint == "every Monday"
    assert j.category_slugs == ["jazz"]


def test_no_all_day_sentinel_times_leak():
    assert all(e.end_time != dt.time(23, 59, 59) for e in _events())
