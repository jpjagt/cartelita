import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers.kami_club import parse_feed

FIXTURE = Path(__file__).parent / "fixtures" / "kami_club_feed.json"

# The fixture was saved on 2026-08-18 and covers the Aug 19-30 line-up; the
# parser filters to today-or-later relative to an injected `today` so the
# test is deterministic against the fixture.
TODAY = dt.date(2026, 8, 18)


def _events():
    return parse_feed(FIXTURE.read_text(), today=TODAY)


def test_parses_the_whole_lineup():
    # The fixture has 15 raw occurrences; two of them (2026-08-23 21:30, two
    # different eventIds) are an exact date+time duplicate that collapses to
    # one occurrence, leaving 14.
    assert len(_events()) == 14


def test_events_have_valid_date_title_url_category():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.start_date >= TODAY
        assert ev.title and ev.title.strip()
        assert ev.source_url.startswith("https://esora.app/hy/yerevan/events/")
        assert ev.category_slugs == ["rock"]


def test_every_event_has_a_real_showtime():
    for ev in _events():
        assert ev.start_time is not None
        assert ev.start_times == [ev.start_time]


def test_external_ids_are_per_occurrence_unique():
    ids = [ev.external_id for ev in _events()]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_same_night_different_showtimes_both_kept():
    # 2026-08-21 has genuinely distinct 21:00 and 22:00 sessions for "Vida De
    # Cuba at Kami" — different clock times, so both must survive (unlike the
    # exact date+time duplicate collapsed above).
    events = [ev for ev in _events() if ev.start_date == dt.date(2026, 8, 21)]
    assert len(events) == 2
    assert {ev.start_time for ev in events} == {dt.time(21, 0), dt.time(22, 0)}


def test_exact_datetime_duplicate_collapses_and_prefers_priced_copy():
    events = [
        ev
        for ev in _events()
        if ev.start_date == dt.date(2026, 8, 23) and ev.start_time == dt.time(21, 30)
    ]
    assert len(events) == 1
    # Both raw duplicates have price=None, so None is the correct outcome —
    # this asserts the collapse happened, not a price value.
    assert events[0].price is None


def test_every_event_has_an_image():
    for ev in _events():
        assert ev.image_url and ev.image_url.startswith("https://esora.app/img/")


def test_prices_follow_the_convention():
    for ev in _events():
        assert ev.price is None or (isinstance(ev.price, str) and ev.price.strip())


def test_price_coverage_is_high():
    # Kami's feed publishes a door price for most nights (only the
    # data-noise duplicate + a couple of second-session slots lack one).
    priced = [ev for ev in _events() if ev.price]
    assert len(priced) / len(_events()) >= 0.6


def test_language_is_never_inferred():
    for ev in _events():
        assert ev.language is None


def test_translations_carry_ru_and_en():
    for ev in _events():
        langs = {t.lang for t in ev.translations}
        assert langs == {"ru", "en"}
        for t in ev.translations:
            assert t.title and t.title.strip()
            assert t.source_url.startswith(f"https://esora.app/{t.lang}/yerevan/events/")


def test_annotations_do_not_leak_the_category_discriminator():
    for ev in _events():
        assert "live_music_other" not in ev.annotations
        assert "rock" not in ev.annotations


def test_past_occurrences_are_filtered():
    events = parse_feed(FIXTURE.read_text(), today=dt.date(2026, 8, 27))
    assert events
    assert all(ev.start_date >= dt.date(2026, 8, 27) for ev in events)
    assert not parse_feed(FIXTURE.read_text(), today=dt.date(2027, 1, 1))


def test_disabled_entities_are_skipped():
    data = json.loads(FIXTURE.read_text())
    occs = data["entities"]["eventOccurrences"]
    first_occ_id = data["result"]["eventOccurrenceIds"][0]
    occs[first_occ_id]["disabledAt"] = "2026-08-18T00:00:00.000Z"
    events = parse_feed(json.dumps(data), today=TODAY)
    assert len(events) == 13
