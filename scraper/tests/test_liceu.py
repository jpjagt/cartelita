import datetime as dt
from pathlib import Path

from cartelera.scrapers.liceu import parse_programme, _category_for, KNOWN_CATEGORIES

FIXTURE = Path(__file__).parent / "fixtures" / "liceu_programme.json"

# The fixture was saved on 2026-06-02; the parser filters to today-or-later
# relative to a `now` we inject so the test is deterministic against the fixture.
NOW = dt.datetime(2026, 6, 2, tzinfo=None)


def _events():
    return parse_programme(FIXTURE.read_text(), today=dt.date(2026, 6, 2))


def test_parses_many_events():
    # One event per upcoming occurrence; the fixture has ~200 future sessions.
    assert len(_events()) >= 150


def test_events_have_valid_date_title_url_category():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.start_date >= dt.date(2026, 6, 2)
        assert ev.title and ev.title.strip()
        assert ev.source_url.startswith("https://www.liceubarcelona.cat/")
        assert len(ev.category_slugs) == 1
        assert ev.category_slugs[0] in KNOWN_CATEGORIES


def test_all_sessions_have_a_real_time():
    # Liceu sessions always carry a wall-clock time (no all-day sentinels).
    for ev in _events():
        assert ev.start_time is not None
        assert ev.start_times == [ev.start_time]


def test_time_offset_correction():
    # The feed's timestamps are 2h behind the displayed wall-clock. "Le nozze di
    # Figaro" on 5 June 2026 must come out as 19:30 (the live detail page value),
    # NOT the raw Madrid reading of 17:30.
    figaro = [
        e for e in _events()
        if e.title == "Le nozze di Figaro" and e.start_date == dt.date(2026, 6, 5)
    ]
    assert figaro, "expected a Figaro occurrence on 2026-06-05"
    assert figaro[0].start_time == dt.time(19, 30)


def test_category_mapping():
    cats = {ev.category_slugs[0] for ev in _events()}
    # An opera house: classical dominates, plus dance / kids / pop strands.
    classical = [e for e in _events() if e.category_slugs[0] == "classical"]
    assert cats <= KNOWN_CATEGORIES
    assert len(classical) > 0
    assert "classical" in cats


def test_category_for_priority():
    # Dance beats kids beats pop beats the classical default; cross-cutting
    # audience tags (LiceUnder35) never decide the category.
    assert _category_for({"Dansa": 1, "Petit Liceu": 1}) == "dance"
    assert _category_for({"Petit Liceu": 1, "LiceuAprèn": 1}) == "kids"
    assert _category_for({"Promotores externes": 1}) == "pop"
    assert _category_for({"Òpera": 1, "LiceUnder35": 1}) == "classical"
    assert _category_for({"Concerts i recitals": 1}) == "classical"
    assert _category_for({"LiceUnder35": 1}) == "classical"


def test_pop_and_dance_present():
    events = _events()
    pop = [e for e in events if e.category_slugs[0] == "pop"]
    dance = [e for e in events if e.category_slugs[0] == "dance"]
    assert pop, "expected external-promoter pop concerts"
    assert dance, "expected dance productions"


def test_translations_present():
    # es/en titles come from the multilingual feed.
    events = _events()
    with_translations = [e for e in events if e.translations]
    assert with_translations, "expected events carrying es/en translations"
    for ev in with_translations:
        langs = {tr.lang for tr in ev.translations}
        assert langs <= {"es", "en"}
        for tr in ev.translations:
            assert tr.title and tr.title.strip()
            if tr.source_url:
                assert tr.source_url.startswith("https://www.liceubarcelona.cat/")


def test_annotations_do_not_leak_category_slugs():
    for ev in _events():
        lowered = {a.lower() for a in ev.annotations}
        for slug in KNOWN_CATEGORIES:
            assert slug not in lowered
        assert ev.category_slugs[0] not in ev.annotations


def test_external_id_unique_per_occurrence():
    events = _events()
    ids = [e.external_id for e in events]
    assert all(ids), "every event must have an external_id"
    assert len(set(ids)) == len(ids), "external_id must be unique per occurrence"
