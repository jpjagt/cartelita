"""Tests for the Nau Ivanow scraper (offline, against saved fixtures)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from cartelera.scrapers.nau_ivanow import (
    _parse_dates,
    _parse_price,
    _parse_time,
    parse_api_events,
)

FIXTURES = Path(__file__).parent / "fixtures"
API_FIXTURE = FIXTURES / "nau_ivanow_api.json"


def _load_api() -> list[dict]:
    return json.loads(API_FIXTURE.read_text())


def _events() -> list:
    return parse_api_events(_load_api())


# ─── date parsing unit tests ──────────────────────────────────────────────────

class TestParseDates:
    def test_de_month(self):
        pub = dt.date(2026, 5, 1)
        assert _parse_dates("Divendres 5 de juny a les 17h", pub) == [dt.date(2026, 6, 5)]

    def test_d_apostrophe_curly(self):
        pub = dt.date(2025, 3, 28)
        # curly apostrophe as in live site
        assert _parse_dates("el divendres 4 d’abril a les 19:00h", pub) == [dt.date(2025, 4, 4)]

    def test_d_apostrophe_straight(self):
        pub = dt.date(2025, 4, 1)
        assert _parse_dates("dissabte 26 d'abril a les 11h", pub) == [dt.date(2025, 4, 26)]

    def test_multiple_dates_multi_session(self):
        pub = dt.date(2025, 4, 9)
        text = "Dilluns 5 de maig Dimarts 6 de maig Dilluns 12 de maig Dimarts 19 de maig"
        dates = _parse_dates(text, pub)
        assert len(dates) == 4
        assert dt.date(2025, 5, 5) in dates
        assert dt.date(2025, 5, 19) in dates

    def test_year_inference_crosses_new_year(self):
        # Publication in Nov 2025, event in March 2026
        pub = dt.date(2025, 11, 6)
        dates = _parse_dates("dissabte 29 de març", pub)
        assert dates == [dt.date(2026, 3, 29)]

    def test_empty_returns_empty(self):
        pub = dt.date(2026, 6, 1)
        assert _parse_dates("Sense data concreta al cos del text.", pub) == []


# ─── price parsing unit tests ─────────────────────────────────────────────────

class TestParsePrice:
    def test_free_gratuites(self):
        assert _parse_price("Inscripcions gratuïtes, aforament limitat") == "free"

    def test_free_gratuit(self):
        assert _parse_price("Preu: GRATUÏT amb inscripció prèvia") == "free"

    def test_soldout(self):
        assert _parse_price("Places esgotades!") == "sold-out"

    def test_euro_price(self):
        assert _parse_price("Preu · 35 € per sessió") == "35€"

    def test_multi_price_returns_max_if_minor_spread(self):
        # 5€ and 35€ → hi/lo = 7 > 2, so range
        result = _parse_price("de 5 € a 35 €")
        assert result == "5–35€"

    def test_none_when_no_signal(self):
        assert _parse_price("Text general sobre l'espectacle.") is None

    def test_none_on_empty(self):
        assert _parse_price("") is None


# ─── time parsing unit tests ──────────────────────────────────────────────────

class TestParseTime:
    def test_a_les_h(self):
        assert _parse_time("Divendres 5 de juny a les 17h a la Nau Ivanow") == dt.time(17, 0)

    def test_a_les_h_mm(self):
        assert _parse_time("el divendres 4 d'abril a les 19:00h") == dt.time(19, 0)

    def test_de_h_a_h(self):
        assert _parse_time("dissabte 26 d'abril · d'11:00h a 12:30") == dt.time(11, 0)

    def test_no_time(self):
        assert _parse_time("Dilluns 28 d'abril a la Nau Ivanow") is None


# ─── integration tests (parse_api_events) ─────────────────────────────────────

class TestParseApiEvents:
    def test_parses_events(self):
        evs = _events()
        assert len(evs) >= 3, "expected at least 3 events from the fixture"

    def test_every_event_has_title_date_url_category(self):
        for ev in _events():
            assert ev.title, f"missing title: {ev}"
            assert isinstance(ev.start_date, dt.date), f"bad date: {ev}"
            assert ev.source_url.startswith("https://nauivanow.com/"), f"bad url: {ev}"
            assert ev.category_slugs, f"missing category: {ev}"
            assert all(s in {"theater", "kids", "dance"} for s in ev.category_slugs), \
                f"unknown category: {ev.category_slugs}"

    def test_open_calls_excluded(self):
        """Events that are convocatòries (open calls) must not appear."""
        evs = _events()
        for ev in evs:
            assert "convocatòria" not in ev.title.lower() or "convoca" not in ev.title.lower(), \
                f"open call leaked into events: {ev.title}"

    def test_kids_events_categorized(self):
        """Events with 'taller familiar' in title must be tagged 'kids'."""
        evs = _events()
        kids = [e for e in evs if "taller familiar" in e.title.lower() or "tallers en famil" in e.title.lower()]
        assert kids, "expected at least one kids/family workshop in fixture"
        for ev in kids:
            assert "kids" in ev.category_slugs, \
                f"family workshop not categorized as kids: {ev.title}"

    def test_price_coverage(self):
        """At least 70% of events should have a price (free events count)."""
        evs = _events()
        with_price = [e for e in evs if e.price is not None]
        pct = len(with_price) / len(evs)
        assert pct >= 0.70, f"price coverage too low: {pct:.0%} ({len(with_price)}/{len(evs)})"

    def test_free_events_present(self):
        """Several events should be free (gratuït)."""
        evs = _events()
        free = [e for e in evs if e.price == "free"]
        assert len(free) >= 2, "expected multiple free events in fixture"

    def test_external_ids_unique(self):
        """All external_ids within the batch must be distinct."""
        evs = _events()
        ids = [e.external_id for e in evs if e.external_id]
        assert len(ids) == len(set(ids)), "duplicate external_ids detected"

    def test_external_ids_qualify_date(self):
        """external_id must contain the date to handle multi-session events."""
        for ev in _events():
            if ev.external_id:
                assert "@" in ev.external_id, \
                    f"external_id lacks date qualifier: {ev.external_id}"

    def test_multi_session_workshop_emits_multiple_events(self):
        """'Llum i Escena' has multiple sessions — we should see at least 3 events for it."""
        evs = _events()
        llum = [e for e in evs if "llum i escena" in e.title.lower()]
        assert len(llum) >= 3, \
            f"expected ≥3 sessions for Llum i Escena, got {len(llum)}"

    def test_image_urls_where_present(self):
        """Events with featured media should have an image URL."""
        evs = _events()
        with_img = [e for e in evs if e.image_url]
        assert len(with_img) >= 3, "expected image URLs on several events"
        for ev in with_img:
            assert ev.image_url.startswith("https://"), f"bad image_url: {ev.image_url}"

    def test_theater_category_on_performance(self):
        """Ça Marche is a theater performance and must be categorized as theater."""
        evs = _events()
        ca_marche = next(
            (e for e in evs if "trabajos forzados" in e.title.lower()), None
        )
        assert ca_marche is not None, "expected Ça Marche event in fixture"
        assert "theater" in ca_marche.category_slugs

    def test_formacio_annotation(self):
        """Formació events should carry a 'formació' annotation."""
        evs = _events()
        form_events = [e for e in evs if "formació" in e.annotations]
        assert form_events, "expected formació events with annotation"
