import datetime as dt
from pathlib import Path
from cartelera.scrapers.jamboree import (
    parse_agenda,
    parse_detail,
    detail_urls_for,
)

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURES / "jamboree_agenda.html"


def _events():
    return parse_agenda(FIXTURE.read_text())


def _detail(lang):
    return (FIXTURES / f"jamboree_event_gigi_{lang}.html").read_text()


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
    assert j.category_slugs == ["jazz"]
    # Recurrence hint is set only for Monday "Jamboree Jam Session" events.
    if j.title.lower() == "jamboree jam session" and j.start_date.weekday() == 0:
        assert j.recurrence_hint == "every Monday"
    else:
        assert j.recurrence_hint is None


def test_recurrence_only_on_jam_session_mondays():
    events = _events()
    for ev in events:
        if ev.recurrence_hint is not None:
            assert ev.title.lower() == "jamboree jam session", (
                f"unexpected recurrence_hint on non-Jam-Session event: {ev.title!r}"
            )
            assert ev.start_date.weekday() == 0, (
                f"recurrence_hint set on non-Monday: {ev.start_date} ({ev.title!r})"
            )


def test_non_monday_jam_events_have_no_recurrence():
    events = _events()
    non_monday_jams = [
        e for e in events
        if "jam session" in e.title.lower() and e.start_date.weekday() != 0
    ]
    for ev in non_monday_jams:
        assert ev.recurrence_hint is None, (
            f"non-Monday jam session got recurrence_hint: {ev.title!r} on {ev.start_date}"
        )


def test_no_all_day_sentinel_times_leak():
    assert all(e.end_time != dt.time(23, 59, 59) for e in _events())


# --- detail-page parsing (translations + multi-showtime) -------------------

def test_detail_urls_derived_from_canonical():
    canonical = "https://jamboreejazz.com/esdeveniment/gigi-mcfarlane-2"
    urls = detail_urls_for(canonical)
    assert urls["ca"] == canonical
    assert urls["es"] == "https://jamboreejazz.com/es/evento/gigi-mcfarlane-2"
    assert urls["en"] == "https://jamboreejazz.com/en/event/gigi-mcfarlane-2"


def test_parse_detail_extracts_title_and_description():
    title, desc, _ = parse_detail(_detail("en"), "en")
    assert title == "Gigi McFarlane"
    assert desc and "vocals" in desc  # English description, not Catalan/Spanish


def test_parse_detail_description_is_language_specific():
    _, ca, _ = parse_detail(_detail("ca"), "ca")
    _, es, _ = parse_detail(_detail("es"), "es")
    _, en, _ = parse_detail(_detail("en"), "en")
    assert "veu" in ca and "voz" in es and "vocals" in en


def test_parse_detail_extracts_multiple_showtimes():
    # The gigi page shows "Horaris: 19:00h / 21:00h" for this date.
    _, _, times = parse_detail(_detail("en"), "en")
    assert times == [dt.time(19, 0), dt.time(21, 0)]


def test_parse_detail_ignores_related_event_showtimes():
    # "You may be interested in" cards carry their own times (19:00/20:30 etc.);
    # those must not bleed into this event's showtimes.
    _, _, times = parse_detail(_detail("ca"), "ca")
    assert dt.time(20, 30) not in times
    assert dt.time(20, 45) not in times
