import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.teatre_victoria import (
    _extract_detail_urls,
    _parse_detail_page,
    _parse_price,
    _parse_start_dt,
    parse_agenda,
)

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA_HTML = FIXTURES / "teatre_victoria_agenda.html"
DETAIL_330 = FIXTURES / "teatre_victoria_330-juan-davila-el-palacio-del-pecado.html"
DETAIL_332 = FIXTURES / "teatre_victoria_332-el-mago-pop.html"

# Detail URL keys as found in the agenda HTML
URL_330 = "https://www.teatrevictoria.com/ca/cartellera/c/330-juan-davila-el-palacio-del-pecado.html"
URL_332 = "https://www.teatrevictoria.com/ca/cartellera/c/332-el-mago-pop.html"


def _detail_pages() -> dict[str, str]:
    return {
        URL_330: DETAIL_330.read_text(),
        URL_332: DETAIL_332.read_text(),
    }


def _all_events():
    return parse_agenda(AGENDA_HTML.read_text(), _detail_pages())


# ── fixture helpers ──────────────────────────────────────────────────────────

def test_agenda_finds_two_shows():
    urls = _extract_detail_urls(AGENDA_HTML.read_text())
    assert len(urls) == 2
    assert all(url.startswith("https://www.teatrevictoria.com/") for _, url in urls)
    show_ids = [sid for sid, _ in urls]
    assert "330" in show_ids
    assert "332" in show_ids


# ── per-show detail parsing ──────────────────────────────────────────────────

def test_detail_330_parses_occurrences():
    events = _parse_detail_page(DETAIL_330.read_text(), "330", URL_330)
    # Juan Dávila had 6 performances (3 weekends)
    assert len(events) >= 3
    for ev in events:
        assert ev.title == "Juan Dávila - El Palacio del Pecado"
        assert isinstance(ev.start_date, dt.date)
        assert ev.start_time is not None
        assert ev.source_url.startswith("https://www.teatrevictoria.com/")
        assert ev.category_slugs == ["theater"]


def test_detail_332_parses_many_occurrences():
    events = _parse_detail_page(DETAIL_332.read_text(), "332", URL_332)
    # El Mago Pop runs ~2 months with 2+ shows/week → many occurrences
    assert len(events) >= 10
    for ev in events:
        assert ev.title == "El Mago Pop"
        assert isinstance(ev.start_date, dt.date)
        assert ev.category_slugs == ["theater"]


# ── full parse ───────────────────────────────────────────────────────────────

def test_parses_at_least_three_events():
    events = _all_events()
    assert len(events) >= 3


def test_every_event_has_title_date_url():
    for ev in _all_events():
        assert ev.title, f"missing title: {ev}"
        assert isinstance(ev.start_date, dt.date), f"bad date: {ev}"
        assert ev.source_url.startswith("https://www.teatrevictoria.com/"), f"bad url: {ev}"


def test_every_event_has_known_category():
    known = {"theater", "dance", "jazz", "classical", "club", "flamenco", "film", "kids", "pop"}
    for ev in _all_events():
        assert ev.category_slugs, f"no category: {ev}"
        for slug in ev.category_slugs:
            assert slug in known, f"unknown category {slug!r}: {ev}"


def test_all_events_are_theater():
    for ev in _all_events():
        assert ev.category_slugs == ["theater"], f"unexpected category: {ev}"


def test_price_coverage():
    events = _all_events()
    # All shows have ticket prices in JSON-LD; expect ≥85% have a price.
    with_price = [e for e in events if e.price]
    assert len(with_price) >= len(events) * 0.85, (
        f"Only {len(with_price)}/{len(events)} events have a price"
    )


def test_sold_out_events_have_sold_out_price():
    # Juan Dávila (show 330) is marked SoldOut in the fixture
    events_330 = _parse_detail_page(DETAIL_330.read_text(), "330", URL_330)
    assert all(e.price == "sold-out" for e in events_330), (
        "All Juan Dávila events should be sold-out"
    )


def test_in_stock_events_have_numeric_price():
    # El Mago Pop (show 332) has price 42€ for most sessions; a handful may
    # be sold-out (which also carries a price in the form "sold-out").
    events_332 = _parse_detail_page(DETAIL_332.read_text(), "332", URL_332)
    priced = [ev for ev in events_332 if ev.price in ("42€", "sold-out")]
    assert len(priced) == len(events_332), (
        f"Unexpected prices: {[ev.price for ev in events_332 if ev.price not in ('42€','sold-out')]}"
    )
    # At least the majority should be available at 42€
    available = [ev for ev in events_332 if ev.price == "42€"]
    assert len(available) >= len(events_332) * 0.8, (
        f"Expected most El Mago Pop sessions to be available, got {len(available)}/{len(events_332)}"
    )


def test_external_ids_are_unique():
    events = _all_events()
    ids = [e.external_id for e in events if e.external_id]
    assert len(ids) == len(set(ids)), (
        f"Duplicate external_ids found: "
        f"{[x for x in ids if ids.count(x) > 1]}"
    )


def test_external_ids_include_date_and_time():
    for ev in _all_events():
        assert ev.external_id, f"missing external_id: {ev}"
        # Format: "330@2026-07-31T2100"
        assert "@" in ev.external_id, f"bad external_id format: {ev.external_id!r}"
        assert "T" in ev.external_id, f"external_id missing time qualifier: {ev.external_id!r}"


def test_image_url_present():
    events = _all_events()
    with_image = [e for e in events if e.image_url]
    assert len(with_image) >= len(events) * 0.9, "Expected images on most events"


def test_start_time_parsed():
    events = _all_events()
    with_time = [e for e in events if e.start_time is not None]
    # All occurrences carry an ISO time in startDate
    assert len(with_time) >= len(events) * 0.9, "Expected most events to have a start_time"


# ── unit tests for helpers ───────────────────────────────────────────────────

def test_parse_start_dt_with_time():
    date, time = _parse_start_dt("2026-10-14T20:30:00+02:00")
    assert date == dt.date(2026, 10, 14)
    assert time == dt.time(20, 30)


def test_parse_start_dt_bare_date():
    date, time = _parse_start_dt("2026-10-14")
    assert date == dt.date(2026, 10, 14)
    assert time is None


def test_parse_price_sold_out():
    assert _parse_price({"offers": {"availability": "https://schema.org/SoldOut", "price": 42}}) == "sold-out"


def test_parse_price_in_stock():
    assert _parse_price({"offers": {
        "availability": "https://schema.org/InStock",
        "price": 42,
        "priceSpecification": {"minPrice": 42, "maxPrice": 42},
    }}) == "42€"


def test_parse_price_free():
    assert _parse_price({"offers": {"price": 0}}) == "free"


def test_parse_price_none():
    assert _parse_price({}) is None
    assert _parse_price({"offers": {}}) is None
