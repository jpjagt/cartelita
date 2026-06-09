from __future__ import annotations

import datetime as dt
from pathlib import Path

from cartelera.scrapers.sat_teatre import (
    parse_programacio,
    parse_detail,
    _parse_price,
    _map_categories,
)

FIXTURES = Path(__file__).parent / "fixtures"
KNOWN_CATEGORIES = {"theater", "dance", "kids", "pop", "classical", "flamenco"}


def _load_all_events():
    """Parse the list + all detail fixtures the way the scraper does."""
    shows = parse_programacio((FIXTURES / "sat_teatre_programacio.html").read_text())
    events = []
    for path in FIXTURES.glob("sat_teatre_detail_*.html"):
        slug = path.name[len("sat_teatre_detail_"):-len(".html")]
        url = f"https://www.sat-teatre.cat/ca/p/c/{slug}.html"
        show = shows.get(url, {})
        events.extend(parse_detail(path.read_text(), show, url))
    return shows, events


def test_programacio_lists_shows():
    shows = parse_programacio((FIXTURES / "sat_teatre_programacio.html").read_text())
    assert len(shows) >= 3
    for url, meta in shows.items():
        assert url.startswith("https://www.sat-teatre.cat/")
        assert meta["title"]
        assert meta["category_slugs"]


def test_parses_many_sessions():
    _shows, events = _load_all_events()
    # 3 shows: PYYKKI (3 sessions) + Girafa (2) + La Julia (2) = 7+ occurrences.
    assert len(events) >= 7


def test_every_event_valid():
    _shows, events = _load_all_events()
    for ev in events:
        assert ev.title
        assert isinstance(ev.start_date, dt.date)
        assert ev.source_url.startswith("https://www.sat-teatre.cat/")
        assert ev.category_slugs
        for slug in ev.category_slugs:
            assert slug in KNOWN_CATEGORIES, slug


def test_external_id_unique_per_occurrence():
    _shows, events = _load_all_events()
    ids = [ev.external_id for ev in events]
    assert all(ids)
    assert len(ids) == len(set(ids)), "external_ids must be unique per occurrence"


def test_same_show_multiple_sessions_distinct_ids():
    """PYYKKI runs 3 sessions across 2 dates -> 3 distinct external_ids."""
    _shows, events = _load_all_events()
    pyykki = [e for e in events if "PYYKKI" in e.title]
    assert len(pyykki) == 3
    assert len({e.external_id for e in pyykki}) == 3
    # Two sessions share a date (03 jul 16:00 + 19:00) but differ in time/id.
    dates = sorted({e.start_date for e in pyykki})
    assert len(dates) == 2


def test_price_coverage():
    _shows, events = _load_all_events()
    with_price = [e for e in events if e.price]
    assert len(with_price) / len(events) >= 0.9
    for e in with_price:
        assert e.price == "12€" or e.price.endswith("€") or e.price in {"free", "sold-out"}


def test_start_times_present():
    _shows, events = _load_all_events()
    with_time = [e for e in events if e.start_time is not None]
    assert len(with_time) / len(events) >= 0.9


def test_kids_category_for_familiar():
    """All three current shows are 'Familiar' -> must carry 'kids'."""
    _shows, events = _load_all_events()
    assert any("kids" in e.category_slugs for e in events)


def test_festival_grec_is_annotation_not_category():
    _shows, events = _load_all_events()
    for e in events:
        assert "Festival Grec" not in e.category_slugs
    assert any("Festival Grec" in e.annotations for e in events)


def test_parse_price_helper():
    assert _parse_price("12 €") == "12€"
    assert _parse_price("Entrada gratuïta") == "free"
    assert _parse_price("Exhaurides") == "sold-out"
    assert _parse_price(None) is None
    assert _parse_price("") is None


def test_map_categories_accented_keys():
    slugs, ann = _map_categories(["Dansa", "Contemporània", "Familiar", "Festival Grec"])
    assert "dance" in slugs
    assert "kids" in slugs
    assert ann == ["Festival Grec"]
