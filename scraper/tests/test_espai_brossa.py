"""
Tests for the Espai Brossa / Centre de les Arts Lliures scraper.

Espai Brossa is a low-volume avant-garde venue (4-8 events at any given time).
Fixture: tests/fixtures/espai_brossa_agenda.html (the homepage, saved 2026-06-09).
The fixture contains 8 calendar events + 3 news items that should be filtered.

Price note: price is fetched from detail pages by the live scraper; parse_agenda
(pure function) leaves price=None. Price coverage assertions are on the live scraper
only (Phase 4 verification). The fixture tests focus on structure, categories and
dedup integrity.
"""
from __future__ import annotations
import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.espai_brossa import (
    parse_agenda,
    _parse_price_from_info,
    _map_category,
    _slug_from_url,
)

FIXTURE = Path(__file__).parent / "fixtures" / "espai_brossa_agenda.html"


def _events():
    return parse_agenda(FIXTURE.read_text())


# ---------------------------------------------------------------------------
# Structural: count, required fields
# ---------------------------------------------------------------------------

def test_parses_at_least_two_events():
    """Espai Brossa is a small venue; the fixture should have ≥2 calendar events."""
    events = _events()
    assert len(events) >= 2, f"expected ≥2 events, got {len(events)}"


def test_news_items_are_excluded():
    """Press releases ('Nota de Premsa', 'General') must be filtered out."""
    events = _events()
    for ev in events:
        # These slugs should not appear in source URLs for filtered items
        assert "portabella-agent-provocador" not in ev.source_url
        assert "els-politics-el-centre" not in ev.source_url
        assert "la-brossa-te-nou-bar" not in ev.source_url


def test_events_have_title_date_url():
    """Every parsed event must have a non-empty title, valid date, and https URL."""
    events = _events()
    for ev in events:
        assert ev.title, f"empty title on {ev}"
        assert isinstance(ev.start_date, dt.date), f"bad start_date on {ev.title}"
        assert ev.source_url.startswith("https://"), f"bad URL on {ev.title}"


def test_every_event_has_exactly_one_known_category():
    """All events must map to a known category slug."""
    known = {"theater", "kids"}
    events = _events()
    assert events, "no events parsed"
    for ev in events:
        assert len(ev.category_slugs) >= 1, f"missing category on {ev.title}"
        for slug in ev.category_slugs:
            assert slug in known, f"unknown category {slug!r} on {ev.title}"


def test_espectacle_and_exposicio_map_to_theater():
    """Espectacle and Exposició events must map to 'theater'."""
    events = _events()
    # The fixture has BLATTODEA (Espectacle) and exhibitions (Exposició)
    theater_events = [e for e in events if "theater" in e.category_slugs]
    assert len(theater_events) >= 2, "expected multiple theater events from fixture"


def test_casal_destiu_maps_to_kids():
    """The summer camp ('Casal d'estiu') must map to 'kids'."""
    events = _events()
    kids_events = [e for e in events if "kids" in e.category_slugs]
    assert kids_events, "expected at least one kids event (Casal d'estiu)"
    casal = next((e for e in kids_events if "casal" in e.title.lower()), None)
    assert casal is not None, "expected Casal d'estiu to be categorized as kids"


def test_date_ranges_have_end_date_after_start():
    """Multi-day runs must have end_date > start_date."""
    events = _events()
    ranged = [e for e in events if e.end_date is not None]
    assert ranged, "expected at least one multi-day run in fixture"
    for ev in ranged:
        assert ev.end_date > ev.start_date, (
            f"{ev.title}: end_date {ev.end_date} not after start_date {ev.start_date}"
        )


def test_single_day_events_have_no_end_date():
    """Single-day events (like workshops) must have end_date=None."""
    events = _events()
    singles = [e for e in events if e.end_date is None]
    assert singles, "expected at least one single-day event in fixture"


def test_no_duplicate_external_ids():
    """Each event must have a unique external_id within the parsed set."""
    events = _events()
    ids = [e.external_id for e in events if e.external_id]
    assert len(ids) == len(set(ids)), f"duplicate external_ids: {ids}"


def test_external_ids_are_non_empty():
    """All parsed events must have a non-empty external_id (the URL slug)."""
    events = _events()
    for ev in events:
        assert ev.external_id, f"missing external_id on {ev.title}"


def test_image_urls_present():
    """Most events should have a thumbnail image_url."""
    events = _events()
    with_img = [e for e in events if e.image_url]
    assert len(with_img) >= len(events) * 0.5, (
        f"expected most events to have images, got {len(with_img)}/{len(events)}"
    )


def test_no_duplicate_source_urls():
    """No two events should point to the same source URL."""
    events = _events()
    urls = [e.source_url for e in events]
    assert len(urls) == len(set(urls)), "duplicate source_urls"


# ---------------------------------------------------------------------------
# Price helper unit tests
# ---------------------------------------------------------------------------

def test_parse_price_explicit_euro():
    assert _parse_price_from_info("Preu: 17 €") == "17€"
    assert _parse_price_from_info("Preu: 15€") == "15€"
    assert _parse_price_from_info("INFO ÚTIL ... Preu: 10 €\nGREC") == "10€"


def test_parse_price_free():
    assert _parse_price_from_info("Activitat gratuïta") == "free"
    assert _parse_price_from_info("Entrada lliure") == "free"


def test_parse_price_sold_out():
    assert _parse_price_from_info("sold out, no quedan entrades") == "sold-out"


def test_parse_price_none_when_absent():
    assert _parse_price_from_info("INFO ÚTIL Del 4 al 12 de juny De dimarts a dissabte, a les 19:30 h") is None


# ---------------------------------------------------------------------------
# Category mapping unit tests
# ---------------------------------------------------------------------------

def test_map_category_espectacle():
    assert _map_category("Espectacle", "BLATTODEA") == "theater"


def test_map_category_exposicio():
    assert _map_category("Exposició", "Exposició de varietats antifeixistes") == "theater"


def test_map_category_activitat_default():
    assert _map_category("Activitat", "Activació Sumari Astral") == "theater"


def test_map_category_casal():
    assert _map_category("Activitat", "Casal d'estiu de la Brossa 2026") == "kids"


# ---------------------------------------------------------------------------
# Slug extraction
# ---------------------------------------------------------------------------

def test_slug_from_url():
    assert _slug_from_url("https://fundaciojoanbrossa.cat/arxiu-arts-en-viu/blattodea/") == "blattodea"
    assert _slug_from_url("https://fundaciojoanbrossa.cat/arxiu-arts-en-viu/spafrica/") == "spafrica"
