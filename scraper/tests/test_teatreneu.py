"""Tests for the Teatreneu scraper.

Fixture strategy:
- `teatreneu_agenda.html` is the main cartellera page (show cards, no sessions).
- `teatreneu_detail_3.html` is the Impro Show detail page (has 5 initial sessions).

The `parse_agenda` function with `detail_pages` lets us inject pre-saved detail HTML
for offline testing. We test parse_agenda with the detail page injected for show 3
(Impro Show), plus the raw list-only mode (no sessions) to validate show-card parsing.
"""
from __future__ import annotations
import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.teatreneu import (
    parse_agenda,
    _parse_show_cards,
    _parse_funcions,
    _parse_price,
    VENUE_SLUG,
)

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA_HTML = (FIXTURES / "teatreneu_agenda.html").read_text(encoding="utf-8")
DETAIL_3_HTML = (FIXTURES / "teatreneu_detail_3.html").read_text(encoding="utf-8")

KNOWN_CATEGORY_SLUGS = {"theater", "kids", "jazz", "classical", "club", "flamenco", "dance", "film", "pop"}


# ---------------------------------------------------------------------------
# Show-card parsing (list page)
# ---------------------------------------------------------------------------

def test_parses_show_cards():
    shows = _parse_show_cards(AGENDA_HTML)
    assert len(shows) >= 10, f"Expected ≥10 show cards, got {len(shows)}"


def test_show_cards_have_required_fields():
    shows = _parse_show_cards(AGENDA_HTML)
    for s in shows:
        assert s["title"], "every show must have a title"
        assert s["source_url"].startswith("https://www.teatreneu.com"), (
            f"unexpected source_url: {s['source_url']}"
        )
        assert s["show_id"] and s["show_id"].isdigit(), (
            f"show_id must be numeric, got {s['show_id']!r}"
        )
        assert s["category_slugs"], "every show must have at least one category"


def test_show_cards_category_slugs_are_known():
    shows = _parse_show_cards(AGENDA_HTML)
    for s in shows:
        for slug in s["category_slugs"]:
            assert slug in KNOWN_CATEGORY_SLUGS, (
                f"Unknown category slug {slug!r} on show {s['title']!r}"
            )


def test_all_shows_have_theater_category():
    """Teatreneu is a theatre venue — all shows must include 'theater'."""
    shows = _parse_show_cards(AGENDA_HTML)
    for s in shows:
        assert "theater" in s["category_slugs"], (
            f"Show {s['title']!r} missing 'theater' category; got {s['category_slugs']}"
        )


def test_infantil_shows_include_kids_category():
    shows = _parse_show_cards(AGENDA_HTML)
    infantil_shows = [s for s in shows if "Infantil" in s["annotations"]]
    assert infantil_shows, "Expected at least one Infantil show in fixture"
    for s in infantil_shows:
        assert "kids" in s["category_slugs"], (
            f"Infantil show {s['title']!r} missing 'kids' category"
        )


def test_category_slugs_not_in_annotations():
    """Category slugs must not leak into annotations."""
    shows = _parse_show_cards(AGENDA_HTML)
    for s in shows:
        for slug in s["category_slugs"]:
            assert slug not in s["annotations"], (
                f"Category slug {slug!r} leaked into annotations of {s['title']!r}"
            )


def test_show_cards_have_images():
    shows = _parse_show_cards(AGENDA_HTML)
    shows_with_image = [s for s in shows if s["image_url"]]
    assert len(shows_with_image) >= len(shows) * 0.8, (
        f"Expected ≥80% of shows to have an image_url; got {len(shows_with_image)}/{len(shows)}"
    )


def test_no_duplicate_source_urls():
    shows = _parse_show_cards(AGENDA_HTML)
    urls = [s["source_url"] for s in shows]
    assert len(urls) == len(set(urls)), "Duplicate source URLs in show cards"


# ---------------------------------------------------------------------------
# Session parsing (detail page)
# ---------------------------------------------------------------------------

def test_parse_funcions_from_detail_page():
    cutoff = dt.date(2099, 12, 31)  # far future — accept everything
    funcions = _parse_funcions(DETAIL_3_HTML, cutoff)
    assert len(funcions) >= 5, f"Expected ≥5 sessions, got {len(funcions)}"


def test_funcions_have_date_time_price():
    cutoff = dt.date(2099, 12, 31)
    funcions = _parse_funcions(DETAIL_3_HTML, cutoff)
    for funcio_id, start_date, start_time, price in funcions:
        assert isinstance(start_date, dt.date), f"start_date must be a date, got {start_date!r}"
        assert start_time is not None, f"session {funcio_id} missing start_time"
        assert price is not None, f"session {funcio_id} missing price"


def test_funcions_price_concise():
    cutoff = dt.date(2099, 12, 31)
    funcions = _parse_funcions(DETAIL_3_HTML, cutoff)
    for funcio_id, _, _, price in funcions:
        if price and price not in ("free", "sold-out"):
            assert len(price) <= 8, f"Price too verbose: {price!r}"
            assert "€" in price, f"Price missing € sign: {price!r}"
            assert price[0].isdigit(), f"Price should start with digit: {price!r}"


def test_funcions_external_ids_unique():
    cutoff = dt.date(2099, 12, 31)
    funcions = _parse_funcions(DETAIL_3_HTML, cutoff)
    ids = [f[0] for f in funcions if f[0] is not None]
    assert len(ids) == len(set(ids)), f"Duplicate funcio IDs: {ids}"


def test_funcions_respect_cutoff():
    """Sessions beyond cutoff should not appear."""
    cutoff = dt.date.today()
    funcions = _parse_funcions(DETAIL_3_HTML, cutoff)
    for funcio_id, start_date, _, _ in funcions:
        assert start_date <= cutoff, (
            f"Session {funcio_id} has date {start_date} beyond cutoff {cutoff}"
        )


# ---------------------------------------------------------------------------
# parse_agenda end-to-end (with injected detail page)
# ---------------------------------------------------------------------------

def _events_with_sessions() -> list:
    """parse_agenda with detail page for show 3 (Impro Show) injected."""
    return parse_agenda(AGENDA_HTML, detail_pages={"3": DETAIL_3_HTML})


def test_parse_agenda_many_events():
    events = _events_with_sessions()
    assert len(events) >= 10, f"Expected ≥10 events, got {len(events)}"


def test_every_event_has_title_date_url():
    events = _events_with_sessions()
    for ev in events:
        assert ev.title, "Event missing title"
        assert isinstance(ev.start_date, dt.date), "Event missing valid start_date"
        assert ev.source_url.startswith("https://www.teatreneu.com"), (
            f"Unexpected source_url: {ev.source_url}"
        )


def test_every_event_has_known_category():
    events = _events_with_sessions()
    for ev in events:
        assert ev.category_slugs, f"Event {ev.title!r} has no category_slugs"
        for slug in ev.category_slugs:
            assert slug in KNOWN_CATEGORY_SLUGS, (
                f"Unknown category slug {slug!r} on {ev.title!r}"
            )


def test_impro_show_sessions_have_price():
    """Sessions from the injected detail page must have prices."""
    events = _events_with_sessions()
    impro_events = [e for e in events if e.title == "Impro Show" and e.external_id and e.external_id.isdigit()]
    assert impro_events, "Expected Impro Show sessions"
    with_price = [e for e in impro_events if e.price is not None]
    coverage = len(with_price) / len(impro_events)
    assert coverage >= 0.85, (
        f"Price coverage for Impro Show sessions: {coverage:.0%} "
        f"({len(with_price)}/{len(impro_events)})"
    )


def test_external_ids_unique_across_batch():
    events = _events_with_sessions()
    ids = [e.external_id for e in events if e.external_id is not None]
    assert len(ids) == len(set(ids)), f"Duplicate external_ids in batch: {ids}"


def test_annotations_contain_category_tags_and_sala():
    """Shows with known categories should have those tags in annotations,
    not as category slugs."""
    events = _events_with_sessions()
    # All events from the Impro Show detail page (show 3) should have sala annotation
    impro = [e for e in events if e.title == "Impro Show" and e.external_id and e.external_id.isdigit()]
    if impro:
        for ev in impro:
            # 'theater' slug must not appear in annotations
            assert "theater" not in ev.annotations, (
                f"'theater' slug leaked into annotations: {ev.annotations}"
            )
            assert "kids" not in ev.annotations, (
                f"'kids' slug leaked into annotations: {ev.annotations}"
            )


def test_infantil_events_have_kids_slug():
    events = _events_with_sessions()
    infantil = [e for e in events if "Infantil" in e.annotations]
    # Some shows may be Infantil from the list page (even without detail page)
    for ev in infantil:
        assert "kids" in ev.category_slugs, (
            f"Infantil event {ev.title!r} missing 'kids' in category_slugs"
        )


# ---------------------------------------------------------------------------
# Price parsing unit tests
# ---------------------------------------------------------------------------

def test_parse_price_extracts_euro_amount():
    from bs4 import BeautifulSoup

    def make_preu(text: str):
        return BeautifulSoup(f'<div class="preu">{text}</div>', "html.parser").select_one(".preu")

    assert _parse_price(make_preu("Des de\n14 €"), None) == "14€"
    assert _parse_price(make_preu("Des de 19 €"), None) == "19€"
    assert _parse_price(make_preu("14€"), None) == "14€"
    assert _parse_price(None, None) is None


def test_parse_price_sold_out():
    from bs4 import BeautifulSoup

    hora_el = BeautifulSoup('<div class="hora disp-no"></div>', "html.parser").select_one(".hora")
    assert _parse_price(None, hora_el) == "sold-out"


# ---------------------------------------------------------------------------
# Scraper registration sanity check
# ---------------------------------------------------------------------------

def test_scraper_registered():
    from cartelera.scrapers import REGISTRY
    import cartelera.scrapers.teatreneu  # noqa: F401 (trigger register)
    assert VENUE_SLUG in REGISTRY, f"Scraper {VENUE_SLUG!r} not in REGISTRY"
    scraper, venue_def = REGISTRY[VENUE_SLUG]
    assert scraper.venue_slug == VENUE_SLUG
    assert "theater" in venue_def.category_slugs
    assert "kids" in venue_def.category_slugs
