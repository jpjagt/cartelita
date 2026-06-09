"""Offline tests for the TNC scraper.

Fixtures:
  tests/fixtures/tnc_agenda.html         — 2026-27 season list page
  tests/fixtures/tnc_agenda_2526.html    — 2025-26 season list page
  tests/fixtures/tnc_detail_el_cadell.html  — detail page with price range
  tests/fixtures/tnc_detail_exhaurit.html   — detail page for sold-out show
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.tnc import (
    parse_agenda,
    _parse_price_from_detail,
    _is_finished,
    _build_event,
    BASE_URL,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
KNOWN_CATEGORIES = {"film", "jazz", "classical", "theater", "club", "flamenco", "dance", "kids", "pop"}


@pytest.fixture(scope="module")
def agenda_html_2627() -> str:
    return (FIXTURE_DIR / "tnc_agenda.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def agenda_html_2526() -> str:
    return (FIXTURE_DIR / "tnc_agenda_2526.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def detail_html_cadell() -> str:
    return (FIXTURE_DIR / "tnc_detail_el_cadell.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def detail_html_exhaurit() -> str:
    return (FIXTURE_DIR / "tnc_detail_exhaurit.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# parse_agenda — list page parsing
# ---------------------------------------------------------------------------

class TestParseAgenda2627:
    def test_parses_at_least_10_events(self, agenda_html_2627):
        events = parse_agenda(agenda_html_2627)
        assert len(events) >= 10, f"Expected >=10, got {len(events)}"

    def test_every_event_has_title(self, agenda_html_2627):
        events = parse_agenda(agenda_html_2627)
        for ev in events:
            assert ev["title"], f"Empty title: {ev}"

    def test_every_event_has_valid_start_date(self, agenda_html_2627):
        events = parse_agenda(agenda_html_2627)
        for ev in events:
            assert isinstance(ev["start_date"], dt.date), f"Bad date: {ev}"
            assert ev["start_date"] >= dt.date(2026, 1, 1), f"Date too old: {ev}"

    def test_every_event_has_source_url(self, agenda_html_2627):
        events = parse_agenda(agenda_html_2627)
        for ev in events:
            assert ev["source_url"].startswith("https://"), f"Bad URL: {ev}"

    def test_node_ids_are_unique(self, agenda_html_2627):
        events = parse_agenda(agenda_html_2627)
        ids = [ev["node_id"] for ev in events]
        assert len(ids) == len(set(ids)), "Duplicate node_ids found"

    def test_finished_shows_excluded(self, agenda_html_2627):
        events = parse_agenda(agenda_html_2627)
        for ev in events:
            # No 2025 dates should appear in the 26-27 fixture (all 26-27 shows)
            assert ev["start_date"].year >= 2026, f"Old show in 2627 fixture: {ev}"

    def test_sala_annotations_captured(self, agenda_html_2627):
        events = parse_agenda(agenda_html_2627)
        # At least some shows should have sala info
        salas = [ev["sala"] for ev in events if ev["sala"]]
        assert len(salas) >= 5, f"Expected sala on at least 5 events, got {len(salas)}"

    def test_images_present_on_most_events(self, agenda_html_2627):
        events = parse_agenda(agenda_html_2627)
        with_image = sum(1 for ev in events if ev["image_url"])
        assert with_image / len(events) >= 0.7, f"Only {with_image}/{len(events)} have images"


class TestParseAgenda2526:
    def test_finished_shows_excluded(self, agenda_html_2526):
        events = parse_agenda(agenda_html_2526)
        for ev in events:
            # No events with "finalitzat" in the status should survive
            assert "finalitzat" not in (ev.get("status_badge") or "").lower(), \
                f"Finished show leaked through: {ev['title']}"

    def test_only_active_shows_present(self, agenda_html_2526):
        events = parse_agenda(agenda_html_2526)
        # The 25-26 season page has ~5 active shows (rest are finalitzat)
        # This count may change; just ensure it's > 0
        assert len(events) >= 1, "Expected at least 1 active show in 25-26 season"

    def test_sold_out_show_has_exhaurit_status(self, agenda_html_2526):
        events = parse_agenda(agenda_html_2526)
        exhaurit_shows = [ev for ev in events if ev.get("status_badge") == "Exhaurit"]
        assert len(exhaurit_shows) >= 1, "Expected at least one Exhaurit show in 25-26"


# ---------------------------------------------------------------------------
# Price parsing from detail page
# ---------------------------------------------------------------------------

class TestParsePriceFromDetail:
    def test_parses_price_range(self, detail_html_cadell):
        price = _parse_price_from_detail(detail_html_cadell)
        # El Cadell: "De 14 € a 28 €" → 28 >= 2*14, so "14–28€"
        assert price is not None
        assert "€" in price

    def test_price_is_range_or_max(self, detail_html_cadell):
        price = _parse_price_from_detail(detail_html_cadell)
        # format_eur_range(14, 28) → "14–28€" (28 >= 2*14)
        assert price == "14–28€", f"Unexpected price: {price}"

    def test_exhaurit_detail_has_price(self, detail_html_exhaurit):
        # Even sold-out shows may have a price on their detail page
        price = _parse_price_from_detail(detail_html_exhaurit)
        # May or may not have price; just assert it doesn't crash
        assert price is None or "€" in price


# ---------------------------------------------------------------------------
# _build_event — assembles ScrapedEvent
# ---------------------------------------------------------------------------

class TestBuildEvent:
    def _raw(self, **overrides) -> dict:
        base = {
            "node_id": "1234",
            "title": "Test Show",
            "href": "/ca/test-show",
            "source_url": "https://www.tnc.cat/ca/test-show",
            "start_date": dt.date(2026, 10, 1),
            "end_date": dt.date(2026, 11, 1),
            "sala": "Sala Gran",
            "status_badge": None,
            "image_url": "https://www.tnc.cat/img/test.jpg",
        }
        base.update(overrides)
        return base

    def test_category_is_theater(self):
        ev = _build_event(self._raw(), price="20€")
        assert ev.category_slugs == ["theater"]

    def test_category_is_known(self):
        ev = _build_event(self._raw(), price="20€")
        for slug in ev.category_slugs:
            assert slug in KNOWN_CATEGORIES, f"Unknown category: {slug}"

    def test_price_preserved(self):
        ev = _build_event(self._raw(), price="14–28€")
        assert ev.price == "14–28€"

    def test_exhaurit_becomes_sold_out(self):
        ev = _build_event(self._raw(status_badge="Exhaurit"), price="20€")
        assert ev.price == "sold-out"

    def test_sala_in_annotations(self):
        ev = _build_event(self._raw(sala="Sala Petita"), price="20€")
        assert "Sala Petita" in ev.annotations

    def test_external_id_is_node_id(self):
        ev = _build_event(self._raw(node_id="9999"), price="10€")
        assert ev.external_id == "9999"

    def test_no_category_slug_leaking_in_annotations(self):
        ev = _build_event(self._raw(), price="20€")
        for ann in ev.annotations:
            assert ann not in KNOWN_CATEGORIES, f"Category slug leaked into annotations: {ann}"


# ---------------------------------------------------------------------------
# Combined: both seasons together
# ---------------------------------------------------------------------------

class TestCombinedSeasons:
    def test_combined_at_least_15_events(self, agenda_html_2526, agenda_html_2627):
        from cartelera.scrapers.tnc import parse_agenda
        events_2526 = parse_agenda(agenda_html_2526)
        events_2627 = parse_agenda(agenda_html_2627)
        total = len(events_2526) + len(events_2627)
        assert total >= 15, f"Combined events {total} < 15"

    def test_all_external_ids_unique_across_seasons(self, agenda_html_2526, agenda_html_2627):
        """Ensure no node_id collision between the two season pages."""
        events_2526 = parse_agenda(agenda_html_2526)
        events_2627 = parse_agenda(agenda_html_2627)
        all_ids = [ev["node_id"] for ev in events_2526 + events_2627]
        assert len(all_ids) == len(set(all_ids)), "Duplicate node_ids across seasons"
