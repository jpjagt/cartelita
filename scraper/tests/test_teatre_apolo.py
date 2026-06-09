"""Offline tests for the Teatre Apolo scraper.

Tests run against saved HTML fixtures and do not make network requests.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.teatre_apolo import (
    parse_agenda,
    parse_detail_price,
    _parse_dates,
    _categories_for_card,
)

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA_HTML = FIXTURES / "teatre_apolo_agenda.html"
TARZAN_DETAIL_HTML = FIXTURES / "teatre_apolo_detail_tarzan.html"

KNOWN_CATEGORIES = {"theater", "dance", "pop", "kids", "flamenco", "classical", "jazz", "film", "club"}


def _events():
    return parse_agenda(AGENDA_HTML.read_text())


# ── Basic structural tests ─────────────────────────────────────────────────────

def test_parses_many_events():
    events = _events()
    # Teatre Apolo typically has 10–35 shows active at once.
    assert len(events) >= 10, f"Expected >=10 events, got {len(events)}"


def test_every_event_has_title():
    for ev in _events():
        assert ev.title, f"Missing title for event: {ev}"


def test_every_event_has_valid_date():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date), f"Bad start_date: {ev}"
        if ev.end_date is not None:
            assert isinstance(ev.end_date, dt.date), f"Bad end_date: {ev}"
            assert ev.end_date >= ev.start_date, (
                f"end_date before start_date: {ev.start_date} > {ev.end_date} for {ev.title!r}"
            )


def test_every_event_has_source_url():
    for ev in _events():
        assert ev.source_url.startswith("https://teatreapolo.com/"), (
            f"Bad source_url: {ev.source_url!r}"
        )


def test_every_event_has_a_known_category():
    for ev in _events():
        assert ev.category_slugs, f"No category slugs for {ev.title!r}"
        for slug in ev.category_slugs:
            assert slug in KNOWN_CATEGORIES, (
                f"Unknown category slug {slug!r} for {ev.title!r}"
            )


def test_external_ids_are_unique():
    events = _events()
    ids = [ev.external_id for ev in events if ev.external_id]
    assert len(ids) == len(set(ids)), "Duplicate external_ids found"


def test_external_id_derived_from_url_slug():
    for ev in _events():
        assert ev.external_id, f"Missing external_id for {ev.title!r}"
        # external_id should be the last path component of the URL
        expected_slug = ev.source_url.rstrip("/").rsplit("/", 1)[-1]
        assert ev.external_id == expected_slug, (
            f"external_id mismatch: {ev.external_id!r} != {expected_slug!r}"
        )


def test_events_have_image_url():
    events = _events()
    with_image = [ev for ev in events if ev.image_url]
    # Nearly all cards have an image
    assert len(with_image) >= len(events) * 0.9, (
        f"Only {len(with_image)}/{len(events)} events have image_url"
    )


# ── Category discriminator tests ──────────────────────────────────────────────

def test_musical_maps_to_theater():
    events = _events()
    # Tarzán is a musical → theater
    tarzan = next((ev for ev in events if "Tarzán" in ev.title or "Tarzan" in ev.title), None)
    assert tarzan is not None, "Tarzán event not found"
    assert "theater" in tarzan.category_slugs, f"Expected theater for Tarzán, got {tarzan.category_slugs}"


def test_danza_maps_to_dance():
    events = _events()
    lake = next((ev for ev in events if "lago de los cisnes" in ev.title.lower()), None)
    assert lake is not None, "Swan Lake event not found"
    assert "dance" in lake.category_slugs, f"Expected dance for Swan Lake, got {lake.category_slugs}"


def test_flamenco_danza_maps_to_flamenco():
    events = _events()
    flamenco = next(
        (ev for ev in events if "flamenco" in ev.title.lower() or "flamenca" in ev.title.lower()),
        None,
    )
    assert flamenco is not None, "No flamenco event found"
    assert "flamenco" in flamenco.category_slugs, (
        f"Expected flamenco for {flamenco.title!r}, got {flamenco.category_slugs}"
    )


def test_concert_maps_to_pop():
    events = _events()
    concert = next(
        (ev for ev in events if "concierto" in ev.title.lower()
         or "michael" in ev.title.lower()
         or "tribute" in ev.title.lower()),
        None,
    )
    if concert:
        assert "pop" in concert.category_slugs, (
            f"Expected pop for concert {concert.title!r}, got {concert.category_slugs}"
        )


def test_infantil_maps_to_kids():
    events = _events()
    kids = [ev for ev in events if "kids" in ev.category_slugs]
    assert kids, "Expected at least one kids event"


# ── Date parsing unit tests ───────────────────────────────────────────────────

def test_parse_dates_simple_range():
    result = _parse_dates("Del 11 al 14 de junio de 2026")
    assert result == (dt.date(2026, 6, 11), dt.date(2026, 6, 14))


def test_parse_dates_cross_month_range():
    result = _parse_dates("Del 22 de julio al 2 de agosto de 2026")
    assert result == (dt.date(2026, 7, 22), dt.date(2026, 8, 2))


def test_parse_dates_cross_year_range():
    result = _parse_dates("Del 26 de noviembre de 2026 al 31 de enero de 2027")
    assert result == (dt.date(2026, 11, 26), dt.date(2027, 1, 31))


def test_parse_dates_single_date_with_weekday():
    result = _parse_dates("Martes 9 de junio de 2026")
    assert result == (dt.date(2026, 6, 9), None)


def test_parse_dates_single_date_no_weekday():
    result = _parse_dates("17 de octubre de 2026")
    assert result == (dt.date(2026, 10, 17), None)


def test_parse_dates_two_dates_same_month():
    result = _parse_dates("3 y 10 de julio de 2026")
    assert result == (dt.date(2026, 7, 3), dt.date(2026, 7, 10))


def test_parse_dates_two_dates_diff_months():
    result = _parse_dates("20 de octubre y 17 de noviembre de 2026")
    assert result == (dt.date(2026, 10, 20), dt.date(2026, 11, 17))


def test_parse_dates_alternative_connector():
    result = _parse_dates("19 de junio a 15 de agosto de 2026")
    assert result == (dt.date(2026, 6, 19), dt.date(2026, 8, 15))


def test_parse_dates_january_2027():
    result = _parse_dates("4 de enero de 2027")
    assert result == (dt.date(2027, 1, 4), None)


def test_parse_dates_invalid_returns_none():
    assert _parse_dates("Sin fecha") is None
    assert _parse_dates("") is None


# ── Price parsing unit tests ──────────────────────────────────────────────────

def test_parse_detail_price_from_fixture():
    html = TARZAN_DETAIL_HTML.read_text()
    price = parse_detail_price(html)
    assert price == "30€", f"Expected 30€, got {price!r}"


def test_parse_detail_price_standard():
    html = '<div class="elementor-widget-text-editor"><div class="elementor-widget-container">Mejor Precio 25€</div></div>'
    assert parse_detail_price(html) == "25€"


def test_parse_detail_price_with_free():
    html = '<div class="elementor-widget-text-editor"><div class="elementor-widget-container">Entrada gratuita</div></div>'
    assert parse_detail_price(html) == "free"


def test_parse_detail_price_none_when_absent():
    html = "<html><body><p>No price here</p></body></html>"
    assert parse_detail_price(html) is None


def test_parse_detail_price_sold_out():
    html = '<div class="elementor-widget-text-editor"><div class="elementor-widget-container">Sold Out</div></div>'
    assert parse_detail_price(html) == "sold-out"


# ── Multi-date range events ───────────────────────────────────────────────────

def test_range_events_have_end_date():
    events = _events()
    # Most events are runs (date ranges), not single-day
    ranged = [ev for ev in events if ev.end_date is not None]
    assert ranged, "Expected at least some events with end_date"
    for ev in ranged:
        assert ev.end_date > ev.start_date


def test_single_date_events_have_no_end_date():
    events = _events()
    singles = [ev for ev in events if ev.end_date is None]
    assert singles, "Expected some single-date events"


# ── Price coverage justification ──────────────────────────────────────────────
# Note: parse_agenda() returns events with price=None (prices require detail
# page fetches). The scrape() method enriches prices via _enrich_prices().
# Price coverage is verified against the live site in Phase 4 and tested with
# the Tarzan detail fixture above.

def test_parse_agenda_returns_none_price():
    """parse_agenda() does not include prices — they're fetched separately."""
    events = _events()
    assert all(ev.price is None for ev in events), (
        "parse_agenda() should return price=None for all events"
    )
