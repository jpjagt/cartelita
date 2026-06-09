"""Offline tests for the La Poderosa scraper.

All tests run against the saved fixture (tests/fixtures/la_poderosa_home.html)
and make no network requests.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.la_poderosa import parse_home

FIXTURE = Path(__file__).parent / "fixtures" / "la_poderosa_home.html"
KNOWN_CATEGORY_SLUGS = {"dance", "theater"}


@pytest.fixture(scope="module")
def fixture_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def events(fixture_html: str):
    return parse_home(fixture_html)


def test_parses_events(events):
    # The fixture homepage carries 9 teaser cards.
    assert len(events) == 9


def test_every_event_has_core_fields(events):
    for e in events:
        assert e.title and e.title.strip()
        assert isinstance(e.start_date, dt.date)
        assert e.source_url.startswith("https://lapoderosa.es/ca/event/")
        assert e.category_slugs, f"{e.title} has no category"
        for slug in e.category_slugs:
            assert slug in KNOWN_CATEGORY_SLUGS, f"unknown category {slug!r}"


def test_image_coverage(events):
    # Every teaser on this venue carries an event image.
    with_img = [e for e in events if e.image_url]
    assert len(with_img) == len(events)
    for e in with_img:
        assert e.image_url.startswith("http")


def test_category_is_dance(events):
    # La Poderosa is a dance house; all events map to dance.
    assert all("dance" in e.category_slugs for e in events)


def test_tipus_kept_as_annotation(events):
    # The site `tipus` label is preserved as an annotation, not leaked into slugs.
    annotated = [e for e in events if e.annotations]
    assert annotated, "expected tipus labels captured as annotations"
    # A known type from the fixture.
    assert any("Performance" in e.annotations for e in events)


def test_external_id_per_occurrence_unique(events):
    ids = [e.external_id for e in events]
    assert all(ids)
    assert len(ids) == len(set(ids)), "external_ids must be unique per occurrence"
    # external_id is qualified with date + time.
    for e in events:
        assert "@" in e.external_id and "T" in e.external_id


def test_all_day_sentinel_time_is_none(events):
    # The 'Trasnmissió' card starts at 00:00:00 -> time unknown -> None.
    found = [e for e in events if e.start_time is None]
    assert found, "expected at least one all-day (time-unknown) event"


def test_price_absent_for_this_venue(events):
    # Price is never published by La Poderosa (see SOURCE.md).
    assert all(e.price is None for e in events)


def test_range_event_has_end_date(events):
    # At least one event spans a date range (start != end).
    ranged = [e for e in events if e.end_date and e.end_date != e.start_date]
    assert ranged, "expected at least one multi-day event with an end_date"
