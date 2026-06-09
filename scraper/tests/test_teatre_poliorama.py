"""Tests for the Teatre Poliorama scraper.

All tests run offline against saved HTML fixtures — no network access.
"""
from __future__ import annotations
import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.teatre_poliorama import (
    parse_agenda,
    parse_detail,
    _map_category,
    _format_price,
    _show_slug_from_url,
)

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA_HTML = (FIXTURES / "teatre_poliorama_agenda.html").read_text()
DETAIL_MICHAELS = (FIXTURES / "teatre_poliorama_detail_875.html").read_text()
DETAIL_FLAMENCO = (FIXTURES / "teatre_poliorama_detail_738.html").read_text()
DETAIL_KIDS = (FIXTURES / "teatre_poliorama_detail_877.html").read_text()

MICHAELS_URL = "https://www.teatrepoliorama.com/ca/programacio/c/875-michaels-legacy.html"
FLAMENCO_URL = "https://www.teatrepoliorama.com/ca/programacio/c/738-gran-gala-flamenco.html"
KIDS_URL = "https://www.teatrepoliorama.com/ca/programacio/c/877-queenmania.html"


# ---------------------------------------------------------------------------
# Agenda page parsing
# ---------------------------------------------------------------------------

def test_agenda_parses_multiple_shows():
    shows = parse_agenda(AGENDA_HTML)
    assert len(shows) >= 10, f"expected ≥10 shows, got {len(shows)}"


def test_agenda_shows_have_urls_and_categories():
    for url, slugs in parse_agenda(AGENDA_HTML):
        assert url.startswith("https://www.teatrepoliorama.com/"), f"bad url: {url}"
        assert slugs, f"no category slugs for {url}"
        for s in slugs:
            assert s in {"theater", "flamenco", "kids", "dance", "jazz", "pop", "classical"}, \
                f"unknown slug {s!r} for {url}"


def test_agenda_no_duplicate_show_urls():
    shows = parse_agenda(AGENDA_HTML)
    urls = [u for u, _ in shows]
    assert len(urls) == len(set(urls)), "duplicate show URLs in agenda"


def test_flamenco_show_maps_to_flamenco():
    shows = parse_agenda(AGENDA_HTML)
    flamenco_shows = [(u, s) for u, s in shows if "flamenco" in u]
    assert flamenco_shows, "expected at least one flamenco show"
    for _, slugs in flamenco_shows:
        assert "flamenco" in slugs, f"flamenco show not categorized as flamenco: {slugs}"


def test_kids_show_maps_to_kids():
    shows = parse_agenda(AGENDA_HTML)
    # Queenmania (Petit Poliorama) should be kids
    kids_shows = [(u, s) for u, s in shows if "queenmania" in u]
    assert kids_shows, "expected queenmania kids show"
    for _, slugs in kids_shows:
        assert "kids" in slugs, f"kids show not categorized as kids: {slugs}"


# ---------------------------------------------------------------------------
# Detail page parsing (Michael's Legacy)
# ---------------------------------------------------------------------------

def test_detail_michaels_parses_events():
    events = parse_detail(DETAIL_MICHAELS, MICHAELS_URL, ["theater"])
    assert len(events) >= 5, f"expected ≥5 occurrences, got {len(events)}"


def test_detail_michaels_all_events_have_required_fields():
    events = parse_detail(DETAIL_MICHAELS, MICHAELS_URL, ["theater"])
    for ev in events:
        assert ev.title, "missing title"
        assert isinstance(ev.start_date, dt.date), "missing start_date"
        assert ev.source_url == MICHAELS_URL, "wrong source_url"
        assert ev.category_slugs, "missing category_slugs"


def test_detail_michaels_has_price_coverage():
    events = parse_detail(DETAIL_MICHAELS, MICHAELS_URL, ["theater"])
    with_price = [e for e in events if e.price is not None]
    assert len(with_price) >= len(events) * 0.85, \
        f"price coverage {len(with_price)}/{len(events)} < 85%"


def test_detail_michaels_prices_are_concise():
    events = parse_detail(DETAIL_MICHAELS, MICHAELS_URL, ["theater"])
    for ev in events:
        if ev.price and ev.price not in ("free", "sold-out"):
            assert len(ev.price) <= 10, f"price too verbose: {ev.price!r}"
            assert "€" in ev.price, f"price missing € symbol: {ev.price!r}"


def test_detail_michaels_external_ids_are_unique():
    events = parse_detail(DETAIL_MICHAELS, MICHAELS_URL, ["theater"])
    ids = [e.external_id for e in events if e.external_id]
    assert len(ids) == len(set(ids)), "duplicate external_ids in Michael's Legacy"
    assert len(ids) == len(events), "some events missing external_id"


def test_detail_michaels_external_ids_are_per_occurrence():
    """external_id must include date+time so multiple sessions on same day are distinct."""
    events = parse_detail(DETAIL_MICHAELS, MICHAELS_URL, ["theater"])
    for ev in events:
        assert ev.external_id, "missing external_id"
        # Must contain a date component
        assert re.search(r"\d{4}-\d{2}-\d{2}", ev.external_id), \
            f"external_id missing date: {ev.external_id!r}"


def test_detail_michaels_has_image():
    events = parse_detail(DETAIL_MICHAELS, MICHAELS_URL, ["theater"])
    with_img = [e for e in events if e.image_url]
    assert with_img, "expected at least one event with image_url"


def test_detail_michaels_has_start_time():
    events = parse_detail(DETAIL_MICHAELS, MICHAELS_URL, ["theater"])
    with_time = [e for e in events if e.start_time is not None]
    assert len(with_time) >= len(events) * 0.8, \
        f"expected ≥80% events with start_time, got {len(with_time)}/{len(events)}"


# ---------------------------------------------------------------------------
# Detail page: Flamenco (Gran Gala Flamenco)
# ---------------------------------------------------------------------------

def test_detail_flamenco_parses_many_events():
    events = parse_detail(DETAIL_FLAMENCO, FLAMENCO_URL, ["flamenco"])
    assert len(events) >= 10, f"expected ≥10 flamenco occurrences, got {len(events)}"


def test_detail_flamenco_category():
    events = parse_detail(DETAIL_FLAMENCO, FLAMENCO_URL, ["flamenco"])
    for ev in events:
        assert ev.category_slugs == ["flamenco"]


def test_detail_flamenco_external_ids_unique():
    events = parse_detail(DETAIL_FLAMENCO, FLAMENCO_URL, ["flamenco"])
    ids = [e.external_id for e in events if e.external_id]
    assert len(ids) == len(set(ids)), "duplicate external_ids in flamenco show"


# ---------------------------------------------------------------------------
# Detail page: Kids (Queenmania — Petit Poliorama)
# ---------------------------------------------------------------------------

def test_detail_kids_parses_events():
    events = parse_detail(DETAIL_KIDS, KIDS_URL, ["kids"])
    assert len(events) >= 1, f"expected ≥1 kids event"


def test_detail_kids_category():
    events = parse_detail(DETAIL_KIDS, KIDS_URL, ["kids"])
    for ev in events:
        assert ev.category_slugs == ["kids"]


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

def test_map_category():
    assert _map_category("Flamenco") == "flamenco"
    assert _map_category("Petit Poliorama") == "kids"
    assert _map_category("Nits del Polio") == "theater"
    assert _map_category("TEMPORADA 2025/26") == "theater"
    assert _map_category("TEMPORADA 2026/27") == "theater"
    assert _map_category("Unknown Label") == "theater"


def test_format_price():
    assert _format_price(0, _INSTOCK) == "free"
    assert _format_price(15.5, _INSTOCK) == "15.5€"
    assert _format_price(17.0, _INSTOCK) == "17€"
    assert _format_price(None, _INSTOCK) is None
    assert _format_price(10, "https://schema.org/SoldOut") == "sold-out"
    assert _format_price(10, "https://schema.org/OutOfStock") == "sold-out"


def test_show_slug_from_url():
    url = "https://www.teatrepoliorama.com/ca/programacio/c/875-michaels-legacy.html"
    assert _show_slug_from_url(url) == "875-michaels-legacy"


def test_all_events_title_non_empty():
    """Every event from every fixture must have a non-empty title."""
    all_events = (
        parse_detail(DETAIL_MICHAELS, MICHAELS_URL, ["theater"])
        + parse_detail(DETAIL_FLAMENCO, FLAMENCO_URL, ["flamenco"])
        + parse_detail(DETAIL_KIDS, KIDS_URL, ["kids"])
    )
    for ev in all_events:
        assert ev.title.strip(), f"empty title in {ev!r}"


def test_all_events_valid_dates():
    all_events = (
        parse_detail(DETAIL_MICHAELS, MICHAELS_URL, ["theater"])
        + parse_detail(DETAIL_FLAMENCO, FLAMENCO_URL, ["flamenco"])
        + parse_detail(DETAIL_KIDS, KIDS_URL, ["kids"])
    )
    for ev in all_events:
        assert isinstance(ev.start_date, dt.date)
        assert 2020 <= ev.start_date.year <= 2030, f"suspicious date: {ev.start_date}"


import re  # noqa: E402 (used in test above, re-imported here for clarity)

_INSTOCK = "https://schema.org/InStock"
