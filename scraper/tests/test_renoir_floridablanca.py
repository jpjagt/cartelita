import datetime as dt
from pathlib import Path

from cartelera.scrapers.renoir_floridablanca import parse_cartelera, DEFAULT_PRICE

FIXTURE = Path(__file__).parent / "fixtures" / "renoir_floridablanca_agenda.html"


def _events():
    return parse_cartelera(FIXTURE.read_text())


def test_parses_many_events():
    # One day's cartelera, one event per (film × showtime) — many sessions.
    events = _events()
    assert len(events) >= 20


def test_events_have_dates_titles_urls_and_film_category():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("https://www.cinesrenoir.com/pelicula/")
        # Single-category venue: every screening is film.
        assert ev.category_slugs == ["film"]


def test_date_comes_from_the_pages_selected_day():
    # The fixture is the day picker's selected option: 2026-06-01.
    for ev in _events():
        assert ev.start_date == dt.date(2026, 6, 1)


def test_every_event_has_a_showtime():
    for ev in _events():
        assert ev.start_time is not None
        assert isinstance(ev.start_time, dt.time)


def test_price_coverage():
    # Cartelera carries no per-screening price; the static general-admission range
    # is applied to every event as free text (never parsed to a number).
    events = _events()
    assert events
    for ev in events:
        assert ev.price == DEFAULT_PRICE
        assert "€" in ev.price


def test_external_id_is_unique_per_occurrence():
    # Each occurrence is a session; the pillalas pase id is unique per session, so
    # the upsert (which dedups on external_id) never collapses two screenings.
    events = _events()
    ids = [e.external_id for e in events]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_external_id_is_the_pase_id():
    for ev in _events():
        assert ev.external_id.startswith("pase-")
        assert ev.external_id.removeprefix("pase-").isdigit()


def test_multiple_sessions_per_film_are_distinct_events():
    # A film with several showtimes yields several events sharing one source_url
    # but distinct external_ids and times.
    events = _events()
    by_url: dict[str, list] = {}
    for ev in events:
        by_url.setdefault(ev.source_url, []).append(ev)
    multi = [evs for evs in by_url.values() if len(evs) > 1]
    assert multi, "expected at least one film with multiple sessions"
    for evs in multi:
        times = [e.start_time for e in evs]
        ids = [e.external_id for e in evs]
        assert len(set(ids)) == len(ids)
        assert len(set(times)) == len(times)


def test_image_urls_are_absolute_and_https():
    for ev in _events():
        assert ev.image_url
        assert ev.image_url.startswith("https://")


def test_version_or_age_captured_as_annotation():
    events = _events()
    annotated = [e for e in events if e.annotations]
    # Nearly every screening lists a version (VOSE/VOSC) and/or age rating.
    assert len(annotated) >= len(events) * 0.9
    flat = {a for e in events for a in e.annotations}
    assert any("Versión" in a for a in flat)


def test_description_holds_director_line():
    events = _events()
    with_dir = [e for e in events if e.description]
    assert len(with_dir) >= len(events) * 0.9
    assert any(e.description.lower().startswith("de ") for e in events)


def test_known_film_present_with_sessions():
    # Find by predicate, not index (fixture data is volatile day to day).
    events = _events()
    ev = next(e for e in events if e.source_url.endswith("/pelicula/calle-malaga/"))
    assert ev.title == "CALLE MÁLAGA"
    assert ev.start_date == dt.date(2026, 6, 1)
    assert ev.category_slugs == ["film"]
