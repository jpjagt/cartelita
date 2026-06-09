"""Tests for the Balañá group theater scrapers (Tívoli, Coliseum, Borràs)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.balana import (
    parse_shows,
    _category_for_genre,
    _make_external_id,
    _parse_sessions_from_detail_html,
)

FIXTURES = Path(__file__).parent / "fixtures"

KNOWN_CATEGORIES = {"theater", "dance", "kids", "pop", "classical", "jazz", "film", "club", "flamenco"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tivoli_events():
    return parse_shows((FIXTURES / "balana_tivoli_api.json").read_text())


def _coliseum_events():
    return parse_shows((FIXTURES / "balana_coliseum_api.json").read_text())


def _borras_events():
    return parse_shows((FIXTURES / "balana_borras_api.json").read_text())


# ---------------------------------------------------------------------------
# Basic parse tests — each venue
# ---------------------------------------------------------------------------

def test_tivoli_parses_events():
    events = _tivoli_events()
    assert len(events) >= 3, f"Tívoli: expected ≥3 events, got {len(events)}"


def test_coliseum_parses_events():
    events = _coliseum_events()
    assert len(events) >= 3, f"Coliseum: expected ≥3 events, got {len(events)}"


def test_borras_parses_events():
    events = _borras_events()
    assert len(events) >= 3, f"Borràs: expected ≥3 events, got {len(events)}"


# ---------------------------------------------------------------------------
# Field validity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("events_fn,venue", [
    (_tivoli_events, "tivoli"),
    (_coliseum_events, "coliseum"),
    (_borras_events, "borras"),
])
def test_events_have_valid_fields(events_fn, venue):
    events = events_fn()
    for ev in events:
        assert ev.title, f"{venue}: event missing title"
        assert isinstance(ev.start_date, dt.date), f"{venue}: bad start_date on {ev.title!r}"
        assert ev.source_url.startswith("https://www.balanaenviu.com/espectaculo/"), \
            f"{venue}: bad source_url {ev.source_url!r}"
        assert len(ev.category_slugs) >= 1, f"{venue}: {ev.title!r} has no category"
        for slug in ev.category_slugs:
            assert slug in KNOWN_CATEGORIES, f"{venue}: unknown category {slug!r} on {ev.title!r}"


def test_start_times_are_valid():
    all_events = _tivoli_events() + _coliseum_events() + _borras_events()
    for ev in all_events:
        if ev.start_time is not None:
            assert isinstance(ev.start_time, dt.time), f"bad start_time on {ev.title!r}"


# ---------------------------------------------------------------------------
# Category coverage
# ---------------------------------------------------------------------------

def test_every_event_has_known_category():
    all_events = _tivoli_events() + _coliseum_events() + _borras_events()
    assert all_events, "expected events from all three venues"
    for ev in all_events:
        assert ev.category_slugs, f"no category on {ev.title!r}"
        for slug in ev.category_slugs:
            assert slug in KNOWN_CATEGORIES, f"unknown category {slug!r} on {ev.title!r}"


def test_theater_is_predominant_category():
    all_events = _tivoli_events() + _coliseum_events() + _borras_events()
    theater_count = sum(1 for e in all_events if "theater" in e.category_slugs)
    # Theater venues: the majority of events should be theater category.
    assert theater_count >= len(all_events) * 0.5, \
        f"expected ≥50% theater events, got {theater_count}/{len(all_events)}"


def test_dance_events_are_categorized():
    # Dansa (genre_id=6) must map to dance, not theater.
    all_events = _tivoli_events() + _coliseum_events() + _borras_events()
    dance_events = [e for e in all_events if "dance" in e.category_slugs]
    # The fixture has dance events (e.g. El Llac dels Cignes, Dance High Escool).
    assert dance_events, "expected at least one dance event across fixtures"


def test_kids_events_are_categorized():
    # Infantil (genre_id=11) must map to kids.
    all_events = _tivoli_events() + _coliseum_events() + _borras_events()
    kids_events = [e for e in all_events if "kids" in e.category_slugs]
    assert kids_events, "expected at least one kids event (Infantil genre)"


# ---------------------------------------------------------------------------
# Category discriminator unit tests
# ---------------------------------------------------------------------------

def test_genre_to_category_mapping():
    assert _category_for_genre({"id": 5, "name": {"ca": "Comèdia"}}) == "theater"
    assert _category_for_genre({"id": 6, "name": {"ca": "Dansa"}}) == "dance"
    assert _category_for_genre({"id": 7, "name": {"ca": "Monòlegs"}}) == "theater"
    assert _category_for_genre({"id": 9, "name": {"ca": "Musical"}}) == "theater"
    assert _category_for_genre({"id": 10, "name": {"ca": "Ponència"}}) == "theater"
    assert _category_for_genre({"id": 11, "name": {"ca": "Infantil"}}) == "kids"
    # Unknown genre defaults to theater.
    assert _category_for_genre({"id": 999, "name": {"ca": "Unknown"}}) == "theater"
    assert _category_for_genre(None) == "theater"


# ---------------------------------------------------------------------------
# Annotations — no category slug leak
# ---------------------------------------------------------------------------

def test_no_category_slug_in_annotations():
    all_events = _tivoli_events() + _coliseum_events() + _borras_events()
    for ev in all_events:
        for annotation in ev.annotations:
            # The human genre label (e.g. "Dansa") is fine as an annotation; the
            # category slug ("dance") must never leak in.
            for slug in KNOWN_CATEGORIES:
                assert slug != annotation, \
                    f"category slug {slug!r} leaked into annotations of {ev.title!r}"


# ---------------------------------------------------------------------------
# Price — systemically unavailable on this site
# ---------------------------------------------------------------------------

def test_price_is_none_or_sold_out():
    """Price is not available on balanaenviu.com — must always be None or 'sold-out'."""
    all_events = _tivoli_events() + _coliseum_events() + _borras_events()
    for ev in all_events:
        assert ev.price in (None, "sold-out"), \
            f"unexpected price {ev.price!r} on {ev.title!r}"


# ---------------------------------------------------------------------------
# external_id uniqueness per venue
# ---------------------------------------------------------------------------

def test_tivoli_external_ids_unique():
    events = _tivoli_events()
    ids = [e.external_id for e in events]
    assert all(ids), "every event must have an external_id"
    assert len(ids) == len(set(ids)), f"duplicate external_ids in Tívoli: {ids}"


def test_coliseum_external_ids_unique():
    events = _coliseum_events()
    ids = [e.external_id for e in events]
    assert all(ids), "every event must have an external_id"
    assert len(ids) == len(set(ids)), f"duplicate external_ids in Coliseum: {ids}"


def test_borras_external_ids_unique():
    events = _borras_events()
    ids = [e.external_id for e in events]
    assert all(ids), "every event must have an external_id"
    assert len(ids) == len(set(ids)), f"duplicate external_ids in Borràs: {ids}"


# ---------------------------------------------------------------------------
# external_id format
# ---------------------------------------------------------------------------

def test_external_id_format():
    eid = _make_external_id("mamma-mia", dt.date(2026, 9, 26), dt.time(17, 0))
    assert eid == "balana-mamma-mia@2026-09-26T1700"

    eid_no_time = _make_external_id("patti-lupone", dt.date(2026, 6, 12), None)
    assert eid_no_time == "balana-patti-lupone@2026-06-12T0000"


# ---------------------------------------------------------------------------
# Detail-page session parser
# ---------------------------------------------------------------------------

def test_parse_detail_sessions_patti_lupone():
    detail_html = (FIXTURES / "balana_detail_patti_lupone.html").read_text()
    sessions = _parse_sessions_from_detail_html(detail_html)
    assert len(sessions) >= 1
    for date, time, href in sessions:
        assert isinstance(date, dt.date)


def test_parse_detail_sessions_la_promesa():
    detail_html = (FIXTURES / "balana_detail_la_promesa.html").read_text()
    sessions = _parse_sessions_from_detail_html(detail_html)
    # La Promesa runs from May to July with many sessions.
    assert len(sessions) >= 5, \
        f"expected ≥5 sessions for la-promesa, got {len(sessions)}"
    dates = {s[0] for s in sessions}
    assert len(dates) >= 3, "expected sessions spanning multiple dates"


# ---------------------------------------------------------------------------
# Cancelled shows are dropped
# ---------------------------------------------------------------------------

def test_cancelled_shows_are_excluded():
    # Antonio Carmona was CANCEL·LAT in the Tívoli fixture.
    events = _tivoli_events()
    titles = [e.title for e in events]
    assert not any("Carmona" in t for t in titles), \
        "cancelled show (Antonio Carmona) should be excluded"


# ---------------------------------------------------------------------------
# Sold-out shows carry the sold-out price
# ---------------------------------------------------------------------------

def test_soldout_shows_are_marked():
    # 'Una Noche Sin Luna' showed SOLD OUT in the Tívoli fixture listing.
    events = _tivoli_events()
    soldout = [e for e in events if e.price == "sold-out"]
    luna = [e for e in events if "Noche Sin Luna" in e.title or "noche-sin-luna" in e.source_url]
    # If the show is still in the fixture as sold-out, it must carry the price.
    if luna:
        assert all(e.price == "sold-out" for e in luna), \
            "sold-out show must carry price='sold-out'"


# ---------------------------------------------------------------------------
# Paralel-62 stub
# ---------------------------------------------------------------------------

def test_paralel62_returns_empty_list():
    from cartelera.scrapers.balana import Paralel62Scraper
    scraper = Paralel62Scraper()
    assert scraper.scrape() == []
    assert scraper.venue_slug == "paralel-62"
