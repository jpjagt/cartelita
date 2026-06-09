"""Tests for the Teatre Romea scraper.

Tests run offline against saved HTML fixtures. All show detail pages must be
saved alongside the season fixture for the tests to work without network access.

Price is systematically unavailable on teatreromea.cat (only discount policies
are published, no actual ticket prices) — price coverage is expected to be 0%.
"""
import datetime as dt
from pathlib import Path

from cartelera.scrapers.teatre_romea import (
    parse_agenda,
    parse_show,
    _parse_session_date,
    _category_from_classes,
    _extract_show_slug,
    SEASON_URL,
)

FIXTURES = Path(__file__).parent / "fixtures"

# The fixtures we saved during scraper development. If the season changes,
# update these slugs and re-save the fixture files.
SHOW_SLUGS = [
    "una-madre-de-pelicula",
    "el-retrat-de-dorian-gray",
    "el-hijo-de-la-comica",
]

SHOW_URLS = [
    f"https://www.teatreromea.cat/ca/ex/{slug}/" for slug in SHOW_SLUGS
]


def _load_fixtures() -> tuple[str, dict[str, str]]:
    """Load season HTML + per-show HTML from fixtures."""
    season_html = (FIXTURES / "teatre_romea_agenda.html").read_text()
    show_htmls = {}
    for slug, url in zip(SHOW_SLUGS, SHOW_URLS):
        fname = f"teatre_romea_show_{slug.replace('-', '_')}.html"
        path = FIXTURES / fname
        if path.exists():
            show_htmls[url] = path.read_text()
    return season_html, show_htmls


def _all_events():
    season_html, show_htmls = _load_fixtures()
    return parse_agenda(season_html, show_htmls)


# --- Unit tests for helper functions ---

def test_parse_session_date_standard():
    result = _parse_session_date("dimecres, 10/06/2026 - 20:00")
    assert result is not None
    date, time = result
    assert date == dt.date(2026, 6, 10)
    assert time == dt.time(20, 0)


def test_parse_session_date_afternoon():
    result = _parse_session_date("dissabte, 13/06/2026 - 17:30")
    assert result is not None
    date, time = result
    assert date == dt.date(2026, 6, 13)
    assert time == dt.time(17, 30)


def test_parse_session_date_invalid():
    assert _parse_session_date("no date here") is None
    assert _parse_session_date("") is None


def test_category_from_classes_teatre():
    assert _category_from_classes(["grid-item", "dis_11", "espectacle-query__item"]) == "theater"


def test_category_from_classes_comedia():
    assert _category_from_classes(["grid-item", "dis_7", "espectacle-query__item"]) == "theater"


def test_category_from_classes_tragicomedia():
    assert _category_from_classes(["grid-item", "dis_17", "espectacle-query__item"]) == "theater"


def test_category_from_classes_familiar():
    assert _category_from_classes(["grid-item", "dis_4", "espectacle-query__item"]) == "kids"


def test_category_from_classes_default():
    assert _category_from_classes(["grid-item", "unknown"]) == "theater"


def test_extract_show_slug():
    assert _extract_show_slug("https://www.teatreromea.cat/ca/ex/una-madre-de-pelicula/") == "una-madre-de-pelicula"
    assert _extract_show_slug("https://www.teatreromea.cat/ca/ex/el-retrat-de-dorian-gray/") == "el-retrat-de-dorian-gray"
    assert _extract_show_slug("https://example.com/no-match") is None


# --- Integration tests against fixture ---

def test_parses_many_events():
    events = _all_events()
    # Sidebar shows 6-14 sessions per show (may be truncated with "altres dates" link).
    # With 3 fixture shows we expect at least 15 events total.
    assert len(events) >= 15, f"Expected >=15 events, got {len(events)}"


def test_every_event_has_title():
    for ev in _all_events():
        assert ev.title, f"Event missing title: {ev}"
        assert len(ev.title) > 0


def test_every_event_has_valid_date():
    for ev in _all_events():
        assert isinstance(ev.start_date, dt.date), f"Invalid date: {ev}"
        # All events should be in 2026 (current season)
        assert ev.start_date.year >= 2026


def test_every_event_has_start_time():
    for ev in _all_events():
        assert ev.start_time is not None, f"Event missing start_time: {ev.title}"
        assert isinstance(ev.start_time, dt.time)


def test_every_event_has_source_url():
    for ev in _all_events():
        assert ev.source_url.startswith("https://www.teatreromea.cat/"), (
            f"Bad source URL: {ev.source_url}"
        )


def test_every_event_has_known_category():
    known = {"theater", "kids"}
    for ev in _all_events():
        assert len(ev.category_slugs) >= 1, f"No category: {ev.title}"
        for slug in ev.category_slugs:
            assert slug in known, f"Unknown category {slug!r} for {ev.title!r}"


def test_theater_is_primary_category():
    """All current season shows are theater (dis_11=Teatre) — no kids in fixture."""
    events = _all_events()
    theater_events = [e for e in events if "theater" in e.category_slugs]
    # All 3 current shows are dis_11 = theater
    assert len(theater_events) == len(events)


def test_external_ids_are_unique():
    events = _all_events()
    ids = [e.external_id for e in events if e.external_id]
    assert len(ids) == len(set(ids)), f"Duplicate external_ids found: {[x for x in ids if ids.count(x) > 1]}"


def test_external_id_format():
    """external_id must include show slug + ISO date + HHMM time."""
    for ev in _all_events():
        assert ev.external_id is not None, f"Missing external_id: {ev.title}"
        # Format: "<slug>@<YYYY-MM-DD>T<HHMM>"
        assert "@" in ev.external_id
        parts = ev.external_id.split("@")
        assert len(parts) == 2
        slug_part, dt_part = parts
        assert slug_part  # non-empty slug
        assert "T" in dt_part
        date_str, time_str = dt_part.split("T")
        dt.date.fromisoformat(date_str)  # must parse as ISO date
        assert len(time_str) == 4  # HHMM


def test_external_id_matches_event_date_and_time():
    """external_id date+time must match the event's start_date and start_time."""
    for ev in _all_events():
        if ev.external_id and ev.start_time:
            expected_suffix = f"@{ev.start_date.isoformat()}T{ev.start_time.strftime('%H%M')}"
            assert ev.external_id.endswith(expected_suffix), (
                f"external_id {ev.external_id!r} doesn't match date/time for {ev.title!r}"
            )


def test_all_events_have_image():
    """Poster images come from the season list page's img tags."""
    events = _all_events()
    with_image = [e for e in events if e.image_url]
    assert len(with_image) == len(events), "All events should have image_url"


def test_no_category_slug_in_annotations():
    """Category slugs must never leak into annotations."""
    for ev in _all_events():
        for ann in ev.annotations:
            assert ann not in {"theater", "kids", "jazz", "film", "classical"}, (
                f"Category slug leaked into annotations for {ev.title!r}: {ann!r}"
            )


def test_price_systematically_unavailable():
    """Price is not published on teatreromea.cat — all events have price=None."""
    events = _all_events()
    priced = [e for e in events if e.price is not None]
    assert len(priced) == 0, (
        f"Expected no prices (systematically unavailable), but got {len(priced)}: "
        f"{[(e.title, e.price) for e in priced[:3]]}"
    )


def test_same_show_events_share_title_and_url():
    """All sessions for a show must have the same title and source_url."""
    events = _all_events()
    # Group by source_url
    by_url: dict[str, list] = {}
    for ev in events:
        by_url.setdefault(ev.source_url, []).append(ev)

    for url, evs in by_url.items():
        titles = {e.title for e in evs}
        assert len(titles) == 1, f"Multiple titles for {url}: {titles}"


def test_parse_show_unit():
    """parse_show with a saved fixture produces correct sessions."""
    show_html = (FIXTURES / "teatre_romea_show_una_madre_de_pelicula.html").read_text()
    url = "https://www.teatreromea.cat/ca/ex/una-madre-de-pelicula/"
    events = parse_show(
        html=show_html,
        show_url=url,
        title="UNA MADRE DE PELÍCULA",
        image_url="https://example.com/img.jpg",
        category_slug="theater",
        annotations=[],
    )
    # The show ran until June 14; fixture captured near end so 6 sessions remain.
    assert len(events) >= 5
    # Check first event
    first = events[0]
    assert first.title == "UNA MADRE DE PELÍCULA"
    assert first.source_url == url
    assert first.category_slugs == ["theater"]
    assert first.image_url == "https://example.com/img.jpg"
    assert first.start_date >= dt.date(2026, 6, 1)
    assert first.start_time is not None
    assert first.external_id is not None
    assert "una-madre-de-pelicula@" in first.external_id
