"""Tests for the Teatre Goya scraper (offline fixture-based)."""
import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.teatre_goya import (
    parse_season_page,
    parse_show_detail,
    _parse_session_line,
    _parse_ticket_id,
)

FIXTURES = Path(__file__).parent / "fixtures"
SEASON_HTML = (FIXTURES / "teatre_goya_agenda.html").read_text()
TINDER_HTML = (FIXTURES / "teatre_goya_tinder_sorpresa.html").read_text()
ATOM_HTML = (FIXTURES / "teatre_goya_lultim_atom.html").read_text()
BUENROLLISTAS_HTML = (FIXTURES / "teatre_goya_buenrollistas.html").read_text()


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

def test_parse_session_line_standard():
    result = _parse_session_line("divendres, 12/06/2026 - 22:30")
    assert result == (dt.date(2026, 6, 12), dt.time(22, 30))


def test_parse_session_line_morning():
    result = _parse_session_line("dissabte, 13/06/2026 - 20:00")
    assert result == (dt.date(2026, 6, 13), dt.time(20, 0))


def test_parse_session_line_invalid():
    assert _parse_session_line("") is None
    assert _parse_session_line("no date here") is None


def test_parse_ticket_id():
    href = "https://tickets.oneboxtds.com/teatregoya/select/2735825?hl=ca-ES"
    assert _parse_ticket_id(href) == "2735825"


def test_parse_ticket_id_missing():
    assert _parse_ticket_id("https://example.com/events/123") is None


# ---------------------------------------------------------------------------
# Season page parsing
# ---------------------------------------------------------------------------

def test_season_page_parses_shows():
    shows = parse_season_page(SEASON_HTML)
    assert len(shows) >= 3, f"Expected ≥3 shows, got {len(shows)}"


def test_season_page_shows_have_title_and_url():
    shows = parse_season_page(SEASON_HTML)
    for title, url, image_url, label in shows:
        assert title, "Title must be non-empty"
        assert url.startswith("https://www.teatregoya.cat/"), f"Bad URL: {url!r}"


def test_season_page_shows_have_category_labels():
    shows = parse_season_page(SEASON_HTML)
    labeled = [s for s in shows if s[3] is not None]
    assert labeled, "Expected at least some shows with category labels"
    for _, _, _, label in labeled:
        assert label in {"Teatre", "Comèdia", "Monòlegs"}, f"Unknown label: {label!r}"


# ---------------------------------------------------------------------------
# Detail page parsing — Tinder Sorpresa (Monòlegs / dis_12)
# ---------------------------------------------------------------------------

def _tinder_events():
    return parse_show_detail(
        TINDER_HTML,
        source_url="https://www.teatregoya.cat/ca/ex/tinder-sorpresa/",
        title="Tinder sorpresa",
        image_url=None,
        category_annotation="Monòlegs",
    )


def test_tinder_parses_sessions():
    events = _tinder_events()
    assert len(events) >= 3, f"Expected ≥3 sessions, got {len(events)}"


def test_tinder_events_have_dates_and_times():
    events = _tinder_events()
    for ev in events:
        assert isinstance(ev.start_date, dt.date)
        assert isinstance(ev.start_time, dt.time)


def test_tinder_events_have_correct_category():
    events = _tinder_events()
    for ev in events:
        assert ev.category_slugs == ["theater"], f"Bad category: {ev.category_slugs}"


def test_tinder_events_have_external_ids():
    events = _tinder_events()
    for ev in events:
        assert ev.external_id, f"Missing external_id on {ev.start_date}"
    # All external IDs must be unique (no occurrence collapse).
    ids = [ev.external_id for ev in events]
    assert len(ids) == len(set(ids)), f"Duplicate external IDs: {ids}"


def test_tinder_has_source_url():
    for ev in _tinder_events():
        assert ev.source_url == "https://www.teatregoya.cat/ca/ex/tinder-sorpresa/"


def test_tinder_annotation_contains_genre():
    events = _tinder_events()
    for ev in events:
        assert "Monòlegs" in ev.annotations


def test_tinder_image_populated():
    events = _tinder_events()
    # image_url should be set from the detail page poster
    with_img = [ev for ev in events if ev.image_url]
    assert with_img, "Expected at least some events with image_url"


def test_tinder_has_description():
    events = _tinder_events()
    with_desc = [ev for ev in events if ev.description]
    assert with_desc, "Expected description from sinopsi block"


# ---------------------------------------------------------------------------
# Detail page parsing — L'ÚLTIM ÀTOM (Teatre / dis_11)
# ---------------------------------------------------------------------------

def _atom_events():
    return parse_show_detail(
        ATOM_HTML,
        source_url="https://www.teatregoya.cat/ca/ex/lultim-atom/",
        title="L'ÚLTIM ÀTOM",
        image_url=None,
        category_annotation="Teatre",
    )


def test_atom_parses_sessions():
    events = _atom_events()
    assert len(events) >= 3


def test_atom_all_theater_category():
    for ev in _atom_events():
        assert ev.category_slugs == ["theater"]


def test_atom_unique_external_ids():
    events = _atom_events()
    ids = [ev.external_id for ev in events]
    assert len(ids) == len(set(ids)), f"Duplicate external IDs: {ids}"


def test_atom_annotation_is_teatre():
    for ev in _atom_events():
        assert "Teatre" in ev.annotations


# ---------------------------------------------------------------------------
# Detail page parsing — Buenrollistas (Monòlegs / dis_12)
# ---------------------------------------------------------------------------

def _buen_events():
    return parse_show_detail(
        BUENROLLISTAS_HTML,
        source_url="https://www.teatregoya.cat/ca/ex/buenrollistas/",
        title="Buenrollistas",
        image_url=None,
        category_annotation="Monòlegs",
    )


def test_buenrollistas_parses_sessions():
    events = _buen_events()
    assert len(events) >= 3


def test_buenrollistas_unique_external_ids():
    events = _buen_events()
    ids = [ev.external_id for ev in events]
    assert len(ids) == len(set(ids)), f"Duplicate external IDs: {ids}"


# ---------------------------------------------------------------------------
# Cross-show consistency
# ---------------------------------------------------------------------------

def test_all_events_have_required_fields():
    """Every event across all parsed fixtures must have title/date/url/category."""
    all_events = _tinder_events() + _atom_events() + _buen_events()
    assert all_events, "No events parsed at all"
    for ev in all_events:
        assert ev.title, "Missing title"
        assert isinstance(ev.start_date, dt.date), "Missing start_date"
        assert ev.source_url.startswith("https://www.teatregoya.cat/"), f"Bad url: {ev.source_url}"
        assert ev.category_slugs, "Missing category_slugs"
        assert all(slug == "theater" for slug in ev.category_slugs), f"Unknown category: {ev.category_slugs}"


def test_price_coverage():
    """Teatre Goya price is not available on the website (behind ticket system).
    All events must have price=None; this is explicitly documented, not a bug."""
    all_events = _tinder_events() + _atom_events() + _buen_events()
    for ev in all_events:
        assert ev.price is None, f"Unexpected price on {ev.title}: {ev.price!r}"


def test_dates_are_in_future_or_recent():
    """All parsed session dates should be plausible (post-2024)."""
    all_events = _tinder_events() + _atom_events() + _buen_events()
    for ev in all_events:
        assert ev.start_date.year >= 2026, f"Implausibly old date: {ev.start_date}"


def test_times_are_valid():
    all_events = _tinder_events() + _atom_events() + _buen_events()
    for ev in all_events:
        if ev.start_time is not None:
            assert 0 <= ev.start_time.hour <= 23
            assert 0 <= ev.start_time.minute <= 59
