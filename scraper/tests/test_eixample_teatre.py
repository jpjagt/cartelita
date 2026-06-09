"""Tests for the Eixample Teatre scraper (offline, fixture-based)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.eixample_teatre import (
    parse_agenda,
    parse_detail,
    _parse_date,
    _parse_time,
    _parse_price,
    _map_categories,
    BASE_URL,
)

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA_HTML = (FIXTURES / "eixample_teatre_agenda.html").read_text()
BONOBOS_HTML = (FIXTURES / "eixample_teatre_detail_bonobos.html").read_text()
LIVING90_HTML = (FIXTURES / "eixample_teatre_detail_living90.html").read_text()
BONOBOS_URL = f"{BASE_URL}/ca/Bonobos"
LIVING90_URL = f"{BASE_URL}/ca/Livinglos90"


# ---------------------------------------------------------------------------
# parse_agenda
# ---------------------------------------------------------------------------

def test_agenda_parses_shows():
    shows = parse_agenda(AGENDA_HTML)
    assert len(shows) >= 10, "should find at least 10 show cards"


def test_agenda_shows_have_required_fields():
    for show in parse_agenda(AGENDA_HTML):
        assert show["href"].startswith("/ca/"), f"unexpected href: {show['href']}"
        assert show["title"], "title should not be empty"


def test_agenda_excludes_gift_card():
    shows = parse_agenda(AGENDA_HTML)
    titles = [s["title"].lower() for s in shows]
    hrefs = [s["href"].lower() for s in shows]
    assert not any("regala" in h for h in hrefs), "gift card page must be excluded"


def test_agenda_no_duplicate_hrefs():
    shows = parse_agenda(AGENDA_HTML)
    hrefs = [s["href"] for s in shows]
    assert len(hrefs) == len(set(hrefs)), "duplicate show hrefs"


# ---------------------------------------------------------------------------
# parse_detail — Bonobos (4 sessions)
# ---------------------------------------------------------------------------

def _bonobos():
    return parse_detail(BONOBOS_HTML, BONOBOS_URL)


def _living90():
    return parse_detail(LIVING90_HTML, LIVING90_URL)


def test_bonobos_returns_multiple_events():
    events = _bonobos()
    assert len(events) >= 3, f"expected ≥3 Bonobos sessions, got {len(events)}"


def test_events_have_valid_dates():
    for ev in _bonobos() + _living90():
        assert isinstance(ev.start_date, dt.date)
        assert ev.start_date >= dt.date(2026, 1, 1), "dates should be recent/future"


def test_events_have_titles():
    for ev in _bonobos() + _living90():
        assert ev.title, "title must not be empty"
        assert len(ev.title) > 2


def test_events_have_source_urls():
    for ev in _bonobos():
        assert ev.source_url == BONOBOS_URL
    for ev in _living90():
        assert ev.source_url == LIVING90_URL


def test_events_have_known_categories():
    known = {"theater", "kids", "jazz", "film", "classical", "flamenco", "dance", "pop", "club"}
    for ev in _bonobos() + _living90():
        assert ev.category_slugs, "must have at least one category"
        for slug in ev.category_slugs:
            assert slug in known, f"unknown category slug: {slug!r}"


def test_events_have_start_times():
    for ev in _bonobos() + _living90():
        assert ev.start_time is not None, f"expected start_time for {ev.title} on {ev.start_date}"


def test_events_have_prices():
    all_events = _bonobos() + _living90()
    with_price = [e for e in all_events if e.price]
    assert len(with_price) == len(all_events), (
        f"price coverage {len(with_price)}/{len(all_events)} — expected 100%"
    )


def test_price_format_is_concise():
    """Prices should be short strings like '20€', not verbose text."""
    for ev in _bonobos() + _living90():
        if ev.price and ev.price not in ("free", "sold-out"):
            assert len(ev.price) <= 8, f"price too verbose: {ev.price!r}"
            assert "Club" not in ev.price, "club price must not appear in price field"


def test_external_ids_are_unique():
    all_events = _bonobos() + _living90()
    ids = [e.external_id for e in all_events if e.external_id]
    assert len(ids) == len(set(ids)), "duplicate external_ids"


def test_external_id_format():
    """external_id must be per-occurrence: slug@YYYYMMDDTHHmm."""
    import re
    pattern = re.compile(r"^[^@]+@\d{8}T\d{4}$")
    for ev in _bonobos() + _living90():
        assert ev.external_id, "external_id must be set"
        assert pattern.match(ev.external_id), (
            f"unexpected external_id format: {ev.external_id!r}"
        )


def test_bonobos_multiple_sessions_same_day():
    """Bonobos runs 16:00 and 20:30 on the same Saturday — both must be emitted."""
    events = _bonobos()
    dates = [e.start_date for e in events]
    from collections import Counter
    multi = [d for d, n in Counter(dates).items() if n > 1]
    assert multi, "expected multiple sessions on at least one day"


def test_image_url_set():
    for ev in _bonobos():
        assert ev.image_url, "Bonobos events should have image_url"
        assert ev.image_url.startswith("https://"), f"bad image_url: {ev.image_url!r}"


def test_shows_without_sessions_return_empty():
    """A page with no ul.programacion should produce zero events."""
    # Create minimal HTML with no sessions
    minimal_html = """
    <div id="main-ctn">
      <h1>Test Show</h1>
      <div class="fondo-auxiliares">
        <a href="/ca/programacio?id_estilo=8">Comèdia</a>
      </div>
    </div>
    """
    events = parse_detail(minimal_html, "https://www.eixampleteatre.cat/ca/test")
    assert events == [], "shows without sessions must return empty list"


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

def test_parse_date():
    assert _parse_date("12/06/2026") == dt.date(2026, 6, 12)
    assert _parse_date("Dissabte 13/06/2026") == dt.date(2026, 6, 13)
    assert _parse_date("no date here") is None


def test_parse_time():
    assert _parse_time("20:30 h") == dt.time(20, 30)
    assert _parse_time("16:00 h") == dt.time(16, 0)
    assert _parse_time("9:00 h") == dt.time(9, 0)
    assert _parse_time("") is None
    assert _parse_time("no time") is None


def test_parse_price_normal():
    assert _parse_price("20€", "Comprar") == "20€"
    assert _parse_price("23€", "Comprar") == "23€"
    assert _parse_price(None, "Comprar") is None
    assert _parse_price("", "Comprar") is None


def test_parse_price_sold_out():
    assert _parse_price("20€", "Agotado") == "sold-out"
    assert _parse_price("20€", "Sold Out") == "sold-out"


def test_map_categories_theater():
    slugs, anns = _map_categories(["Comèdia", "Teatre"])
    assert "theater" in slugs
    assert "Comèdia" not in anns
    assert "Teatre" not in anns


def test_map_categories_kids():
    slugs, anns = _map_categories(["Familiar", "Humor", "Màgia", "Teatre"])
    assert "kids" in slugs
    assert "theater" in slugs
    assert "Humor" in anns
    assert "Màgia" in anns


def test_map_categories_fallback():
    """No recognized tags → default to theater."""
    slugs, _ = _map_categories([])
    assert slugs == ["theater"]


def test_map_categories_annotation_tags_not_in_slugs():
    slugs, anns = _map_categories(["Humor", "Monòlegs"])
    assert "Humor" in anns or "Monòlegs" in anns
    assert "humor" not in slugs
    assert "monòlegs" not in slugs
