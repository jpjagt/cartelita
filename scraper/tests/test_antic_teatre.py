"""Tests for the Antic Teatre scraper.

All tests run offline against saved HTML fixtures — no network access.
The agenda fixture is the June 2026 monthly programme page; the detail
fixture is the 'Peti-suis' event detail page.
"""
import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.antic_teatre import parse_agenda, parse_detail, _parse_price

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA_HTML = FIXTURES / "antic_teatre_agenda.html"
DETAIL_HTML = FIXTURES / "antic_teatre_detail.html"

KNOWN_CATEGORIES = {"theater", "dance", "film", "jazz", "classical", "club", "flamenco", "kids", "pop"}


def _events():
    """Parse June agenda without detail enrichment (offline mode)."""
    return parse_agenda(AGENDA_HTML.read_text())


def _events_enriched():
    """Parse June agenda enriched with the Peti-suis detail fixture."""
    detail = parse_detail(DETAIL_HTML.read_text())
    detail_cache = {
        "https://www.anticteatre.com/events/event/peti-suis-cia-supreema": detail,
    }
    return parse_agenda(AGENDA_HTML.read_text(), detail_cache=detail_cache)


# ── Basic coverage ─────────────────────────────────────────────────────────────

def test_parses_events_from_fixture():
    events = _events()
    assert len(events) >= 5, f"expected at least 5 events, got {len(events)}"


def test_every_event_has_title_date_url():
    for ev in _events():
        assert ev.title, f"empty title: {ev}"
        assert isinstance(ev.start_date, dt.date), f"bad date: {ev}"
        assert ev.source_url.startswith("https://www.anticteatre.com/"), (
            f"unexpected source_url: {ev.source_url}"
        )


def test_every_event_has_known_category():
    for ev in _events():
        assert len(ev.category_slugs) >= 1, f"no category: {ev.title}"
        for slug in ev.category_slugs:
            assert slug in KNOWN_CATEGORIES, f"unknown category {slug!r} on {ev.title!r}"


def test_venue_is_theater_dominant():
    """Antic Teatre is a performing-arts space; most events must be theater or dance."""
    events = _events()
    theater_dance = [e for e in events if set(e.category_slugs) & {"theater", "dance"}]
    assert len(theater_dance) >= len(events) * 0.9, (
        f"expected ≥90% theater/dance, got {len(theater_dance)}/{len(events)}"
    )


# ── Dates ──────────────────────────────────────────────────────────────────────

def test_all_dates_in_fixture_month():
    """June fixture → all dates must be in June 2026."""
    events = _events()
    for ev in events:
        assert ev.start_date.year == 2026, f"unexpected year: {ev.start_date}"
        assert ev.start_date.month == 6, f"unexpected month: {ev.start_date}"


def test_dates_are_in_valid_range():
    events = _events()
    for ev in events:
        assert 1 <= ev.start_date.day <= 31


# ── Times ─────────────────────────────────────────────────────────────────────

def test_most_events_have_start_time():
    events = _events()
    with_time = [e for e in events if e.start_time is not None]
    assert len(with_time) >= len(events) * 0.5, (
        f"expected ≥50% have start_time, got {len(with_time)}/{len(events)}"
    )


def test_start_times_are_valid():
    for ev in _events():
        if ev.start_time is not None:
            assert 0 <= ev.start_time.hour <= 23
            assert 0 <= ev.start_time.minute <= 59


# ── External IDs ──────────────────────────────────────────────────────────────

def test_all_external_ids_present():
    for ev in _events():
        assert ev.external_id, f"missing external_id: {ev.title} {ev.start_date}"


def test_external_ids_are_per_occurrence_unique():
    """Each event occurrence must have a distinct external_id (dedup key)."""
    events = _events()
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids)), (
        f"duplicate external_ids: {[x for x in ids if ids.count(x) > 1]}"
    )


def test_external_id_contains_date():
    """external_id must include the ISO date so occurrences of the same show differ."""
    for ev in _events():
        assert ev.start_date.isoformat() in ev.external_id, (
            f"date not in external_id {ev.external_id!r} for {ev.title}"
        )


# ── Price ──────────────────────────────────────────────────────────────────────

def test_price_parse_euro_range():
    # Both tiers close together → show only the higher price
    assert _parse_price("15 euros ONLINE // 17 euros TAQUILLA") == "17€"
    assert _parse_price("8,5 euros ONLINE i 10 euros TAQUILLA") == "10€"


def test_price_parse_free():
    assert _parse_price("Entrada gratuïta") == "free"
    assert _parse_price("Activitat gratuïta") == "free"
    assert _parse_price(None) is None
    assert _parse_price("") is None


def test_price_parse_sold_out():
    assert _parse_price("Esgotat") == "sold-out"


def test_price_enriched_from_detail():
    """After enrichment with the Peti-suis detail, those rows must have price."""
    events = _events_enriched()
    peti_suis = [e for e in events if "Peti-suis" in e.title or "peti-suis" in e.external_id]
    assert peti_suis, "expected Peti-suis events in fixture"
    for ev in peti_suis:
        assert ev.price is not None, f"missing price on {ev.title} {ev.start_date}"
        assert ev.price == "17€", f"expected 17€, got {ev.price!r}"


def test_price_is_concise_when_present():
    """When a price is set, it must be a short string, not raw verbose text."""
    for ev in _events_enriched():
        if ev.price and ev.price not in ("free", "sold-out"):
            assert len(ev.price) <= 12, f"price too verbose: {ev.price!r}"
            assert "euros" not in ev.price.lower(), f"raw price: {ev.price!r}"


# ── Detail parsing ────────────────────────────────────────────────────────────

def test_detail_parse_price():
    detail = parse_detail(DETAIL_HTML.read_text())
    assert detail["price"] == "17€"


def test_detail_parse_category():
    detail = parse_detail(DETAIL_HTML.read_text())
    assert detail["category"] in KNOWN_CATEGORIES


def test_detail_parse_image():
    detail = parse_detail(DETAIL_HTML.read_text())
    assert detail["image_url"] and detail["image_url"].startswith("https://")


def test_image_enriched_from_detail():
    events = _events_enriched()
    peti_suis = [e for e in events if "Peti-suis" in e.title or "peti-suis" in e.external_id]
    for ev in peti_suis:
        assert ev.image_url and "wp-content/uploads" in ev.image_url


# ── Annotations ──────────────────────────────────────────────────────────────

def test_annotations_include_author():
    """Most events should have the company/artist in annotations."""
    events = _events()
    with_author = [e for e in events if e.annotations]
    assert len(with_author) >= len(events) * 0.7, (
        f"expected ≥70% events have annotations, got {len(with_author)}/{len(events)}"
    )


def test_category_slug_not_in_annotations():
    """Category slugs ('theater', 'dance') must not leak into annotations."""
    for ev in _events():
        blob = " ".join(ev.annotations).lower()
        assert "theater" not in blob, f"'theater' leaked into annotations: {ev.annotations}"
        assert "dance" not in blob, f"'dance' leaked into annotations: {ev.annotations}"


# ── Regression: no duplicate occurrences ─────────────────────────────────────

def test_same_show_different_dates_have_different_ids():
    """Multiple performances of the same show must get distinct external_ids."""
    events = _events()
    # Peti-suis runs Thu-Sun (4 performances in June)
    peti = [e for e in events if "peti-suis" in e.external_id]
    if len(peti) >= 2:
        ids = [e.external_id for e in peti]
        assert len(ids) == len(set(ids)), "same-show occurrences share an external_id"
