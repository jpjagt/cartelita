import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers.malkhas_jazz_club import parse_feed

FIXTURE = Path(__file__).parent / "fixtures" / "malkhas_jazz_club_feed.json"

# The fixture was saved on 2026-08-18 and covers the week's line-up
# (Aug 18–23); the parser filters to today-or-later relative to an injected
# `today` so the test is deterministic against the fixture.
TODAY = dt.date(2026, 8, 18)


def _events():
    return parse_feed(FIXTURE.read_text(), today=TODAY)


def test_parses_the_whole_week():
    # One ScrapedEvent per nightly occurrence; the fixture week has 6.
    assert len(_events()) == 6


def test_events_have_valid_date_title_url_category():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.start_date >= TODAY
        assert ev.title and ev.title.strip()
        assert ev.source_url.startswith("https://esora.app/hy/yerevan/events/")
        assert ev.category_slugs == ["jazz"]


def test_every_event_has_a_real_showtime():
    # Malkhas sets start nightly at 21:00; the feed always carries startTime.
    for ev in _events():
        assert ev.start_time is not None
        assert ev.start_times == [ev.start_time]


def test_external_ids_are_per_occurrence_unique():
    # One artist plays several nights (same eventId, several occurrences); a
    # coarse external_id would collapse them in the upsert.
    ids = [ev.external_id for ev in _events()]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_repeat_artist_keeps_one_event_page_but_distinct_occurrences():
    events = _events()
    by_url: dict[str, list] = {}
    for ev in events:
        by_url.setdefault(ev.source_url, []).append(ev)
    repeated = [evs for evs in by_url.values() if len(evs) > 1]
    # The fixture week has two artists playing twice each.
    assert repeated, "expected at least one artist with multiple nights"
    for evs in repeated:
        dates = {ev.start_date for ev in evs}
        assert len(dates) == len(evs)  # distinct nights
        assert len({ev.external_id for ev in evs}) == len(evs)


def test_every_event_has_an_image():
    for ev in _events():
        assert ev.image_url and ev.image_url.startswith("https://esora.app/img/")


def test_prices_follow_the_convention():
    # Esora's Malkhas feed publishes no cover charge (price is null); the club
    # takes phone reservations. None = unknown is correct — never a guess.
    for ev in _events():
        assert ev.price is None or (isinstance(ev.price, str) and ev.price.strip())


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


def test_annotations_do_not_leak_the_category():
    for ev in _events():
        assert "jazz" not in ev.annotations
        assert not set(ev.category_slugs) & set(ev.annotations)


def test_past_occurrences_are_filtered():
    events = parse_feed(FIXTURE.read_text(), today=dt.date(2026, 8, 21))
    assert len(events) == 3
    assert all(ev.start_date >= dt.date(2026, 8, 21) for ev in events)
    assert not parse_feed(FIXTURE.read_text(), today=dt.date(2027, 1, 1))


def test_disabled_entities_are_skipped():
    data = json.loads(FIXTURE.read_text())
    occs = data["entities"]["eventOccurrences"]
    first_occ_id = data["result"]["eventOccurrenceIds"][0]
    occs[first_occ_id]["disabledAt"] = "2026-08-18T00:00:00.000Z"
    events = parse_feed(json.dumps(data), today=TODAY)
    assert len(events) == 5
