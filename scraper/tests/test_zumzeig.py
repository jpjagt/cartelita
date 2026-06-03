import datetime as dt
from pathlib import Path
from cartelera.scrapers.zumzeig import parse_agenda

FIXTURE = Path(__file__).parent / "fixtures" / "zumzeig_agenda.html"

# Programming cycles seen on the calendar; all are sub-categories of "film".
KNOWN_CYCLES = {"Paralleles", "Estrenes", "Infantil", "Festivals", "Experimental"}


def _events():
    return parse_agenda(FIXTURE.read_text())


def test_parses_many_events():
    # The calendar shows ~6 weeks (June + July) with one entry per screening.
    events = _events()
    assert len(events) >= 30


def test_events_have_dates_titles_urls_and_film_category():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("https://zumzeigcine.coop/cinema/films/")
        # Single-category venue: every screening is film.
        assert ev.category_slugs == ["film"]


def test_dates_are_in_the_future_window():
    # Fixture captured 2026-06-01; sessions span into July.
    for ev in _events():
        assert dt.date(2026, 6, 1) <= ev.start_date <= dt.date(2026, 8, 31)


def test_every_event_has_a_showtime():
    # `.hora` is always present on a calendar session — the local wall-clock time.
    for ev in _events():
        assert ev.start_time is not None
        assert isinstance(ev.start_time, dt.time)


def test_price_is_none_no_scrapable_price():
    # Zumzeig exposes no scrape-able ticket price; price must be None, not guessed.
    for ev in _events():
        assert ev.price is None


def test_cycle_captured_as_annotation_without_leaking_into_category():
    events = _events()
    # The programming cycle (tipo) is captured as an annotation on (almost) every
    # session, but never leaks into category_slugs.
    annotated = [e for e in events if any(a in KNOWN_CYCLES for a in e.annotations)]
    assert len(annotated) >= len(events) * 0.9
    for ev in events:
        assert ev.category_slugs == ["film"]
        for cyc in KNOWN_CYCLES:
            assert cyc.lower() not in {c.lower() for c in ev.category_slugs}
    cycles = {a for e in events for a in e.annotations}
    assert cycles & KNOWN_CYCLES


def test_external_id_present_and_encodes_occurrence():
    for ev in _events():
        assert ev.external_id
        # filmid qualified by the occurrence's date+time: <id>@YYYY-MM-DDTHHMM
        assert "@" in ev.external_id and "T" in ev.external_id.split("@", 1)[1]


def test_external_id_is_unique_per_occurrence():
    # The same film screens on several dates/times; external_id must distinguish
    # those occurrences (the upsert dedups on it), so all ids are unique. This is
    # the Filmoteca-trap guard.
    events = _events()
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))


def test_a_film_screens_on_multiple_distinct_occurrences():
    # Sanity: at least one film has several screenings, and they survive as
    # distinct events (not collapsed by a coarse external_id).
    events = _events()
    by_url: dict[str, int] = {}
    for ev in events:
        by_url[ev.source_url] = by_url.get(ev.source_url, 0) + 1
    assert max(by_url.values()) >= 2


def test_known_screening_present_with_right_fields():
    # Find by predicate, not by index (calendar data is volatile across captures).
    events = _events()
    ev = next(e for e in events if e.source_url.endswith("/cinema/films/corredora/"))
    assert ev.title == "Corredora"
    assert ev.start_date == dt.date(2026, 6, 2)
    assert ev.start_time == dt.time(12, 0)
    assert "Estrenes" in ev.annotations


def test_accompanied_screening_annotated():
    # The first session (Tot plegat, gran escampall, 1 Jun 18:30*) is an
    # accompanied screening — the `*` becomes an "acompanyat" annotation, and is
    # not left in the time.
    events = _events()
    ev = next(e for e in events if e.source_url.endswith("/cinema/films/tot-plegat-gran-escampall/"))
    assert ev.start_time == dt.time(18, 30)
    assert "acompanyat" in ev.annotations
