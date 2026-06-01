"""Tests for the Casa Figari scraper.

Run offline against the saved schedule image fixture:
    cd scraper && uv run pytest tests/test_casa_figari.py -v

Casa Figari publishes its agenda as a weekly image (PNG/WebP). The scraper
uses Tesseract OCR with bounding-box layout reconstruction. There is no
HTML event list — the fixture is the raw schedule image file.
"""
import datetime as dt
from pathlib import Path

from cartelera.scrapers.casa_figari import parse_schedule, _extract_schedule_image_url

FIXTURE_IMAGE = Path(__file__).parent / "fixtures" / "casa_figari_schedule.png"
FIXTURE_HTML = Path(__file__).parent / "fixtures" / "casa_figari_agenda.html"


def _events() -> list:
    return parse_schedule(FIXTURE_IMAGE.read_bytes())


# ---------------------------------------------------------------------------
# Basic coverage
# ---------------------------------------------------------------------------


def test_parses_multiple_events():
    """The weekly schedule typically has ~10 events (2 per night, Tue–Sat)."""
    events = _events()
    assert len(events) >= 5, f"Expected at least 5 events, got {len(events)}"


def test_events_have_dates_titles_urls():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date), f"start_date is not a date: {ev}"
        assert ev.title, f"Empty title: {ev}"
        assert ev.source_url == "https://www.casafigari.com", f"Bad source_url: {ev.source_url}"
        assert ev.category_slugs[0] in {"jazz", "club"}, f"Unknown category: {ev.category_slugs}"


def test_events_have_start_times():
    """All parsed events must have a start_time (the image always includes it)."""
    events = _events()
    missing_time = [ev for ev in events if ev.start_time is None]
    assert not missing_time, f"Events without start_time: {[ev.title for ev in missing_time]}"


def test_most_events_have_a_price():
    """Price coverage should be high — every event in the image includes one."""
    events = _events()
    with_price = [ev for ev in events if ev.price]
    assert len(with_price) >= len(events) * 0.8, (
        f"Price coverage too low: {len(with_price)}/{len(events)}"
    )


def test_external_ids_are_unique():
    events = _events()
    ids = [ev.external_id for ev in events]
    assert len(set(ids)) == len(ids), f"Duplicate external_ids: {ids}"


def test_external_ids_encode_date_and_time():
    for ev in _events():
        assert ev.external_id, f"Missing external_id: {ev}"
        # Format: YYYY-MM-DD_HHMM
        assert "_" in ev.external_id, f"Bad external_id format: {ev.external_id!r}"


# ---------------------------------------------------------------------------
# Category discriminator
# ---------------------------------------------------------------------------


def test_jazz_events_exist():
    events = _events()
    jazz = [ev for ev in events if ev.category_slugs == ["jazz"]]
    assert jazz, "Expected at least one jazz concert"


def test_club_events_exist():
    events = _events()
    club = [ev for ev in events if ev.category_slugs == ["club"]]
    assert club, "Expected at least one club/DJ night"


def test_dj_events_are_club():
    """Events with 'DJ' in the title should be categorized as club."""
    events = _events()
    dj_events = [ev for ev in events if ev.title.upper().startswith("DJ ")]
    assert dj_events, "Expected at least one 'DJ ...' event in the fixture"
    assert all(ev.category_slugs == ["club"] for ev in dj_events), (
        f"DJ events not all club: {[(ev.title, ev.category_slugs) for ev in dj_events]}"
    )


def test_strictly_vinyl_events_are_club():
    """Events described as 'Strictly Vinyl Discotheque' must be club."""
    events = _events()
    vinyl_nights = [ev for ev in events if "Strictly Vinyl" in " ".join(ev.annotations)]
    assert vinyl_nights, "Expected Strictly Vinyl Discotheque events in fixture"
    assert all(ev.category_slugs == ["club"] for ev in vinyl_nights), (
        f"Vinyl nights not all club: {[(ev.title, ev.category_slugs) for ev in vinyl_nights]}"
    )


def test_jam_session_is_jazz():
    """Jam sessions are live music events → jazz, not club."""
    events = _events()
    jams = [ev for ev in events if "jam session" in ev.title.lower()]
    assert jams, "Expected at least one Jam Session event in fixture"
    assert all(ev.category_slugs == ["jazz"] for ev in jams), (
        f"Jam sessions not all jazz: {[(ev.title, ev.category_slugs) for ev in jams]}"
    )


# ---------------------------------------------------------------------------
# Annotation and description capture
# ---------------------------------------------------------------------------


def test_some_events_have_annotations():
    events = _events()
    annotated = [ev for ev in events if ev.annotations]
    assert annotated, "Expected some events to have annotations (genre/desc)"


def test_annotations_not_empty_strings():
    for ev in _events():
        assert all(a.strip() for a in ev.annotations), (
            f"Empty annotation string in {ev.title!r}: {ev.annotations}"
        )


# ---------------------------------------------------------------------------
# HTML image URL extraction (offline, from saved fixture)
# ---------------------------------------------------------------------------


def test_html_fixture_yields_image_url():
    """The HTML fixture should contain the schedule image URL."""
    html = FIXTURE_HTML.read_text()
    url = _extract_schedule_image_url(html)
    assert url, "Could not find schedule image URL in HTML fixture"
    assert "squarespace" in url or "figari" in url.lower() or "feed" in url.lower(), (
        f"Unexpected image URL: {url!r}"
    )


def test_free_entry_normalized():
    image_bytes = FIXTURE_IMAGE.read_bytes()
    events = parse_schedule(image_bytes)
    # No event should have raw "entrada libre" as price string.
    assert not any(
        e.price and "libre" in e.price.lower() for e in events
    ), "raw 'entrada libre' must be normalized to 'free'"
