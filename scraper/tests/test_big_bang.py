import datetime as dt
from cartelera.scrapers.big_bang import generate_events, LOOKAHEAD_DAYS, SITE_URL

TODAY = dt.date(2026, 6, 1)  # Monday — gives one of each weekday in 14 days


def _events():
    return generate_events(today=TODAY)


def test_generates_correct_number_of_events():
    events = _events()
    # 14 days × 9 slots/week = 18 events total (9 slots / 7 days × 14 days = 18)
    # Mon=1, Tue=1, Wed=1, Thu=1, Fri=2, Sat=2, Sun=1 = 9 per week; 14 days = 2 weeks
    assert len(events) == 18


def test_events_cover_exactly_lookahead_days():
    events = _events()
    dates = {e.start_date for e in events}
    assert min(dates) == TODAY
    assert max(dates) == TODAY + dt.timedelta(days=LOOKAHEAD_DAYS - 1)


def test_events_have_valid_dates_titles_urls():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url == SITE_URL
        assert ev.category_slugs


def test_all_events_have_known_categories():
    for ev in _events():
        for slug in ev.category_slugs:
            assert slug in ("jazz", "club"), f"unexpected category: {slug}"


def test_all_events_are_free():
    for ev in _events():
        assert ev.price == "free"


def test_jazz_events_have_start_times():
    jazz_events = [e for e in _events() if "jazz" in e.category_slugs]
    for ev in jazz_events:
        assert ev.start_time is not None, f"{ev.title} on {ev.start_date} missing start_time"


def test_dj_sessions_have_midnight_start_time():
    dj_events = [e for e in _events() if e.title == "Dj Session"]
    assert dj_events, "expected Dj Session events"
    for ev in dj_events:
        assert ev.start_time == dt.time(0, 0), (
            f"DJ session on {ev.start_date} must have start_time=00:00, got {ev.start_time}"
        )


def test_open_mic_days():
    events = _events()
    open_mic = [e for e in events if e.title == "Big Bang Open Mic"]
    assert open_mic
    for ev in open_mic:
        # Open Mic runs Mon/Wed/Thu/Sun (weekdays 0,2,3,6)
        assert ev.start_date.weekday() in (0, 2, 3, 6)


def test_jazz_jam_on_fridays():
    events = _events()
    jam = [e for e in events if e.title == "Jam Session de Jazz"]
    assert jam
    for ev in jam:
        assert ev.start_date.weekday() == 4  # Friday


def test_new_orleans_jazz_jam_on_saturdays():
    events = _events()
    nola = [e for e in events if e.title == "New Orleans Jazz Jam"]
    assert nola
    for ev in nola:
        assert ev.start_date.weekday() == 5  # Saturday


def test_external_ids_are_unique():
    events = _events()
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))


def test_external_ids_contain_date_and_slug():
    for ev in _events():
        assert ev.external_id
        assert ev.start_date.isoformat() in ev.external_id


def test_open_mic_annotations():
    open_mic = [e for e in _events() if e.title == "Big Bang Open Mic"]
    for ev in open_mic:
        assert "Rock" in ev.annotations
        assert "Blues" in ev.annotations
        assert "Pop" in ev.annotations


def test_dj_sessions_are_club_category():
    dj = [e for e in _events() if e.title == "Dj Session"]
    assert dj
    for ev in dj:
        assert ev.category_slugs == ["club"]


def test_no_duplicate_events_same_date_and_title():
    events = _events()
    seen: set[tuple] = set()
    for ev in events:
        key = (ev.start_date, ev.title)
        assert key not in seen, f"duplicate: {key}"
        seen.add(key)
