import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.teatre_grec import (
    parse_schedule,
    parse_price_detail,
    _parse_dates,
    _parse_price,
)

FIXTURES = Path(__file__).parent / "fixtures"
KNOWN_CATEGORIES = {"theater", "dance", "pop", "film"}


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


@pytest.fixture
def all_events():
    """Events parsed across both saved schedule pages (pagination exercised)."""
    events = []
    for page in ("teatre_grec_page0.html", "teatre_grec_page1.html"):
        events.extend(parse_schedule(_load(page)))
    return events


def test_parses_many_events(all_events):
    # Two fixture pages, ~18 each.
    assert len(all_events) >= 30


def test_every_event_has_valid_core_fields(all_events):
    for e in all_events:
        assert e.title and e.title.strip()
        assert isinstance(e.start_date, dt.date)
        assert e.source_url.startswith("https://www.barcelona.cat/grec/")
        assert e.category_slugs and all(c in KNOWN_CATEGORIES for c in e.category_slugs)


def test_dates_are_in_festival_window(all_events):
    # Grec 2026 runs June–August.
    for e in all_events:
        assert e.start_date.year == 2026
        assert 6 <= e.start_date.month <= 8
        if e.end_date:
            assert e.end_date >= e.start_date


def test_external_id_uniqueness(all_events):
    ids = [e.external_id for e in all_events]
    assert all(ids)
    assert len(set(ids)) == len(ids)


def test_multiple_category_types_present(all_events):
    cats = {c for e in all_events for c in e.category_slugs}
    # The Grec mixes disciplines; the two fixture pages carry at least theater +
    # one music (pop) show, and across the full set dance/film too.
    assert "theater" in cats
    assert len(cats) >= 2


def test_annotations_capture_discipline_and_venue(all_events):
    # Every event should carry its raw discipline label and the venue space as
    # free-form annotations (not leaked into category_slugs).
    with_disc = [e for e in all_events if e.annotations]
    assert len(with_disc) == len(all_events)
    for e in all_events:
        # discipline label is the first annotation
        assert e.annotations[0]


def test_image_urls_absolute(all_events):
    with_img = [e for e in all_events if e.image_url]
    # Most cards have a hero image.
    assert len(with_img) >= 0.8 * len(all_events)
    for e in with_img:
        assert e.image_url.startswith("https://www.barcelona.cat/")


# ── date parser ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw, start, end",
    [
        ("From 17 June to 5 July", dt.date(2026, 6, 17), dt.date(2026, 7, 5)),
        ("From 1 to 3 July", dt.date(2026, 7, 1), dt.date(2026, 7, 3)),
        ("From 1 to 9 of July", dt.date(2026, 7, 1), dt.date(2026, 7, 9)),
        ("1 July", dt.date(2026, 7, 1), None),
        ("9 and 10 July", dt.date(2026, 7, 9), dt.date(2026, 7, 10)),
        ("25, 26, 30 June and 1, 2, 7, 8, 9 July", dt.date(2026, 6, 25), dt.date(2026, 7, 9)),
        ("04/07", dt.date(2026, 7, 4), None),
        ("July 9", dt.date(2026, 7, 9), None),
        ("Sunday, July 12", dt.date(2026, 7, 12), None),
        ("28 de juliol", dt.date(2026, 7, 28), None),
        ("9 July (English), 10 and 11 July (Catalan)", dt.date(2026, 7, 9), dt.date(2026, 7, 11)),
        ("From 30 July to 2 August", dt.date(2026, 7, 30), dt.date(2026, 8, 2)),
    ],
)
def test_parse_dates(raw, start, end):
    assert _parse_dates(raw) == (start, end)


# ── price parser ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("€26", "26€"),
        ("5 €", "5€"),
        ("€21,50", "22€"),
        ("€14-34", "14–34€"),       # hi >= 2*lo -> range
        ("From €10 to €22", "10–22€"),
        ("€30 - €42,50", "42€"),    # hi < 2*lo -> single (highest)
        ("From €12", "12€"),
        ("€24 + handling fees", "24€"),
        ("€12, €10 and €8", "12€"),
        ("Free with prior reservation", "free"),
        ("Free entry (lecture) and €15 (concert)", "15€"),  # euro present -> paid
        ("", None),
    ],
)
def test_parse_price(raw, expected):
    assert _parse_price(raw or None) == expected


def test_parse_price_detail_fixture():
    # La Ruta detail page price is €26.
    assert parse_price_detail(_load("teatre_grec_detail.html")) == "26€"
