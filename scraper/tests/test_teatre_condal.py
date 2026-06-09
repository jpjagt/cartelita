"""Tests for the Teatre Condal scraper.

Architecture: parse_season(html) → list of show dicts (season list page)
              parse_detail(html, show) → list[ScrapedEvent] (per-show detail page)

All tests run offline against saved fixtures.
Price is always None (not available on the venue site).
"""
import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers.teatre_condal import (
    _parse_catalan_date_range,
    parse_detail,
    parse_season,
)

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA = FIXTURES / "teatre_condal_agenda.html"
DETAIL_LAUCA = FIXTURES / "teatre_condal_detail.html"
DETAIL_CARMEN = FIXTURES / "teatre_condal_detail_carmen.html"
DETAIL_ELLA = FIXTURES / "teatre_condal_detail_ella_era_anita.html"
DETAIL_ABONAMENT = FIXTURES / "teatre_condal_detail_abonament.html"
DETAIL_ANDRE = FIXTURES / "teatre_condal_detail_andre.html"
DETAIL_SOLITUDES = FIXTURES / "teatre_condal_detail_solitudes.html"
DETAIL_FOREVER = FIXTURES / "teatre_condal_detail_forever.html"


# ---------------------------------------------------------------------------
# Season listing
# ---------------------------------------------------------------------------


def _shows():
    return parse_season(AGENDA.read_text())


def test_season_parses_multiple_shows():
    shows = _shows()
    # Currently 10 shows on the 2025/26 season page
    assert len(shows) >= 5


def test_season_shows_have_required_fields():
    for show in _shows():
        assert show["title"], "title must be non-empty"
        assert show["url"].startswith("https://www.teatrecondal.cat/"), f"bad URL: {show['url']}"
        assert show["category"] in {"theater", "dance"}, f"unknown category: {show['category']}"
        assert show["slug"], "slug must be non-empty"


def test_season_images_present():
    shows = _shows()
    with_image = [s for s in shows if s.get("image_url")]
    # Most shows have a poster image
    assert len(with_image) >= len(shows) * 0.8


def test_dance_show_mapped_correctly():
    shows = _shows()
    carmen = next((s for s in shows if "Carmen" in s["title"]), None)
    assert carmen is not None, "Carmen (dis_2 / dance) must appear in season list"
    assert carmen["category"] == "dance"


def test_theater_shows_mapped_correctly():
    shows = _shows()
    theater_shows = [s for s in shows if s["category"] == "theater"]
    assert len(theater_shows) >= 5


def test_abonament_bundle_excluded_from_season_parse():
    # Subscription bundles with title prefix "ABONAMENT" must be excluded
    shows = _shows()
    titles = {s["title"].upper() for s in shows}
    assert not any(t.startswith("ABONAMENT") for t in titles), (
        "ABONAMENT show should not appear in parsed shows"
    )


# ---------------------------------------------------------------------------
# Detail page — L'auca del Sr. Pera (multiple sessions)
# ---------------------------------------------------------------------------


def _lauca_show():
    return {
        "title": "L'auca del Sr. Pera",
        "url": "https://www.teatrecondal.cat/ca/ex/lauca-del-senyor-pera/",
        "category": "theater",
        "image_url": "https://vmanager.iseic.net/media/ver/cartell/v4/2026/05/506454ab.jpg",
        "slug": "lauca-del-senyor-pera",
    }


def _lauca_events():
    return parse_detail(DETAIL_LAUCA.read_text(), _lauca_show())


def test_detail_parses_multiple_sessions():
    events = _lauca_events()
    # The fixture has 6 listed sessions
    assert len(events) >= 3


def test_detail_events_have_dates_times():
    for ev in _lauca_events():
        assert isinstance(ev.start_date, dt.date)
        assert isinstance(ev.start_time, dt.time)


def test_detail_events_have_correct_title():
    for ev in _lauca_events():
        assert ev.title == "L'auca del Sr. Pera"


def test_detail_events_have_source_url():
    for ev in _lauca_events():
        assert ev.source_url == "https://www.teatrecondal.cat/ca/ex/lauca-del-senyor-pera/"


def test_detail_events_have_theater_category():
    for ev in _lauca_events():
        assert ev.category_slugs == ["theater"]


def test_detail_events_price_is_none():
    # Price is not available on the venue site — must be None
    for ev in _lauca_events():
        assert ev.price is None


def test_detail_external_ids_are_unique():
    events = _lauca_events()
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids)), "duplicate external_ids detected"


def test_detail_external_ids_use_onebox_format():
    for ev in _lauca_events():
        assert ev.external_id is not None
        assert ev.external_id.startswith("teatre-condal:")
        # The suffix must be a numeric session ID from oneboxtds
        suffix = ev.external_id.split(":", 1)[1]
        assert suffix.isdigit(), f"external_id suffix not numeric: {ev.external_id!r}"


def test_detail_image_url_forwarded():
    events = _lauca_events()
    assert all(e.image_url for e in events)


# ---------------------------------------------------------------------------
# Detail page — Carmen (Ballet / dance)
# ---------------------------------------------------------------------------


def _carmen_show():
    return {
        "title": "Carmen",
        "url": "https://www.teatrecondal.cat/ca/ex/carmen-2/",
        "category": "dance",
        "image_url": "https://example.com/carmen.jpg",
        "slug": "carmen-2",
    }


def _carmen_events():
    return parse_detail(DETAIL_CARMEN.read_text(), _carmen_show())


def test_carmen_has_sessions():
    events = _carmen_events()
    assert len(events) >= 1


def test_carmen_category_is_dance():
    for ev in _carmen_events():
        assert ev.category_slugs == ["dance"]


def test_carmen_has_valid_dates():
    for ev in _carmen_events():
        assert isinstance(ev.start_date, dt.date)
        assert isinstance(ev.start_time, dt.time)


# ---------------------------------------------------------------------------
# Detail page — Ella era Anita (single-session show)
# ---------------------------------------------------------------------------


def _ella_show():
    return {
        "title": "ELLA ERA ANITA",
        "url": "https://www.teatrecondal.cat/ca/ex/ella-era-anita/",
        "category": "theater",
        "image_url": None,
        "slug": "ella-era-anita",
    }


def _ella_events():
    return parse_detail(DETAIL_ELLA.read_text(), _ella_show())


def test_ella_has_exactly_one_session():
    events = _ella_events()
    assert len(events) == 1


def test_ella_session_date():
    ev = _ella_events()[0]
    assert ev.start_date == dt.date(2026, 10, 19)
    assert ev.start_time == dt.time(20, 0)


# ---------------------------------------------------------------------------
# Detail page — Abonament Kulunka (bundle — should be skipped)
# ---------------------------------------------------------------------------


def _abonament_show():
    return {
        "title": "ABONAMENT KULUNKA",
        "url": "https://www.teatrecondal.cat/ca/ex/abonament-kulunka/",
        "category": "theater",
        "image_url": None,
        "slug": "abonament-kulunka",
    }


def test_abonament_bundle_yields_no_events():
    # Subscription bundles have no `.date` span — must be silently skipped
    events = parse_detail(DETAIL_ABONAMENT.read_text(), _abonament_show())
    assert events == [], f"expected 0 events for bundle, got {len(events)}"


# ---------------------------------------------------------------------------
# Detail page fallback — Solitudes / Forever (empty session list)
# ---------------------------------------------------------------------------


def _solitudes_show():
    return {
        "title": "SOLITUDES",
        "url": "https://www.teatrecondal.cat/ca/ex/solitudes/",
        "category": "theater",
        "image_url": None,
        "slug": "solitudes",
        "dates_text": "del 10 al 19 de juliol de 2026",
    }


def _forever_show():
    return {
        "title": "Forever",
        "url": "https://www.teatrecondal.cat/ca/ex/forever/",
        "category": "theater",
        "image_url": None,
        "slug": "forever",
        "dates_text": "del 22 de juliol al 2 d'agost de 2026",
    }


def test_solitudes_fallback_emits_one_event():
    # Solitudes has an empty session list — should fall back to date-range event
    events = parse_detail(DETAIL_SOLITUDES.read_text(), _solitudes_show())
    assert len(events) == 1


def test_solitudes_fallback_date_range():
    ev = parse_detail(DETAIL_SOLITUDES.read_text(), _solitudes_show())[0]
    assert ev.start_date == dt.date(2026, 7, 10)
    assert ev.end_date == dt.date(2026, 7, 19)
    assert ev.start_time is None


def test_forever_fallback_cross_month_range():
    events = parse_detail(DETAIL_FOREVER.read_text(), _forever_show())
    assert len(events) == 1
    ev = events[0]
    assert ev.start_date == dt.date(2026, 7, 22)
    assert ev.end_date == dt.date(2026, 8, 2)


def test_fallback_external_id_format():
    ev = parse_detail(DETAIL_SOLITUDES.read_text(), _solitudes_show())[0]
    assert ev.external_id == "solitudes@2026-07-10"


# ---------------------------------------------------------------------------
# Catalan date range parser unit tests
# ---------------------------------------------------------------------------


def test_catalan_date_single():
    start, end = _parse_catalan_date_range("fins al 28 de juny de 2026")
    assert start == dt.date(2026, 6, 28)
    assert end is None


def test_catalan_date_same_month_range():
    start, end = _parse_catalan_date_range("del 17 al 21 de juny de 2026")
    assert start == dt.date(2026, 6, 17)
    assert end == dt.date(2026, 6, 21)


def test_catalan_date_cross_month_range():
    start, end = _parse_catalan_date_range("del 22 de juliol al 2 d'agost de 2026")
    assert start == dt.date(2026, 7, 22)
    assert end == dt.date(2026, 8, 2)


def test_catalan_date_cross_month_range2():
    start, end = _parse_catalan_date_range("del 12 de febrer al 14 de març de 2027")
    assert start == dt.date(2027, 2, 12)
    assert end == dt.date(2027, 3, 14)


def test_catalan_date_apostrophe():
    start, end = _parse_catalan_date_range("el 19 d'octubre de 2026")
    assert start == dt.date(2026, 10, 19)
    assert end is None


# ---------------------------------------------------------------------------
# Cross-cutting: external_id is per-occurrence
# ---------------------------------------------------------------------------


def test_external_id_encodes_occurrence():
    """Two sessions on the same day (different times) must have different external_ids."""
    events = _lauca_events()
    # Find sessions on the same date
    from collections import defaultdict
    by_date: dict = defaultdict(list)
    for ev in events:
        by_date[ev.start_date].append(ev)
    same_day = [(d, evs) for d, evs in by_date.items() if len(evs) > 1]
    if same_day:
        _, evs = same_day[0]
        ids = [e.external_id for e in evs]
        assert len(set(ids)) == len(ids), "same-day events share external_id"


# ---------------------------------------------------------------------------
# Category: known values only
# ---------------------------------------------------------------------------

KNOWN_CATEGORIES = {"theater", "dance", "jazz", "classical", "film", "kids", "flamenco", "pop", "club"}


def test_all_category_slugs_are_known():
    lauca = _lauca_events()
    carmen = _carmen_events()
    ella = _ella_events()
    for ev in lauca + carmen + ella:
        for cat in ev.category_slugs:
            assert cat in KNOWN_CATEGORIES, f"unknown category: {cat!r}"
