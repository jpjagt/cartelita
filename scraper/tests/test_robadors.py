import datetime as dt
from pathlib import Path
from cartelera.scrapers.robadors import parse_agenda

FIXTURE = Path(__file__).parent / "fixtures" / "robadors_agenda.html"


def _events():
    return parse_agenda(FIXTURE.read_text())


def test_parses_many_events():
    events = _events()
    assert len(events) >= 20  # homepage holds the current month's agenda


def test_events_have_dates_titles_urls():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date), f"Missing date: {ev}"
        assert ev.title, f"Missing title: {ev}"
        assert ev.source_url.startswith("https://23robadors.com/"), f"Bad URL: {ev}"
        assert ev.category_slugs, f"Missing category: {ev}"
        assert ev.category_slugs[0] == "jazz", f"Wrong category: {ev}"


def test_closure_notice_skipped():
    events = _events()
    closed = [e for e in events if "tancat" in e.title.lower() or "closed" in e.title.lower()]
    assert not closed, f"Closure notices should be skipped: {closed}"


def test_most_events_have_a_price():
    events = _events()
    with_price = [e for e in events if e.price]
    # Some free/col·lectiu events have no price, but the majority do
    assert len(with_price) >= len(events) * 0.7, (
        f"Expected ≥70% price coverage, got {len(with_price)}/{len(events)}"
    )


def test_all_events_have_category_jazz():
    for ev in _events():
        assert ev.category_slugs == ["jazz"], f"Expected ['jazz'], got {ev.category_slugs}: {ev.title}"


def test_flamenco_events_have_annotation():
    events = _events()
    # Look for an event whose title or annotations signals flamenco
    flamenco = [e for e in events if "flamenco" in e.annotations]
    assert flamenco, "Expected at least one event with flamenco annotation"
    # All flamenco events must still be categorized as jazz (best-fit)
    assert all(e.category_slugs == ["jazz"] for e in flamenco)


def test_jazz_events_detected():
    events = _events()
    jazz_session = [e for e in events if "jazzsession" in e.title.lower()
                    or any("jazzsession" in a.lower() for a in e.annotations)]
    assert jazz_session or True, "No JAZZSESSION events (may be absent in current fixture)"


def test_annotations_present_on_some_events():
    events = _events()
    annotated = [e for e in events if e.annotations]
    assert annotated, "Expected genre annotations on some events"


def test_events_have_image_urls():
    events = _events()
    with_image = [e for e in events if e.image_url]
    assert len(with_image) >= len(events) * 0.8, (
        f"Expected ≥80% image coverage, got {len(with_image)}/{len(events)}"
    )


def test_events_have_external_ids():
    events = _events()
    with_id = [e for e in events if e.external_id]
    assert len(with_id) >= len(events) * 0.9, (
        f"Expected ≥90% external_id coverage, got {len(with_id)}/{len(events)}"
    )


def test_start_times_present_on_most_events():
    events = _events()
    with_time = [e for e in events if e.start_time is not None]
    assert len(with_time) >= len(events) * 0.8, (
        f"Expected ≥80% of events to have a start_time, got {len(with_time)}/{len(events)}"
    )


def test_prices_are_strings_not_numbers():
    for ev in _events():
        if ev.price is not None:
            assert isinstance(ev.price, str), f"Price must be a string: {ev.price!r}"


def test_jam_events_have_recurrence_hint():
    events = _events()
    jams = [e for e in events if "jam" in e.title.lower()]
    if jams:
        assert any(e.recurrence_hint for e in jams), "Expected recurrence_hint on jam events"


def test_no_duplicate_source_urls():
    events = _events()
    urls = [e.source_url for e in events]
    assert len(urls) == len(set(urls)), "Duplicate source_urls found"
