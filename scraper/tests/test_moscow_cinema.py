import datetime as dt
from pathlib import Path

from cartelera.scrapers.moscow_cinema import (
    _format_price,
    parse_film_detail,
    parse_schedule,
)

FIXTURES = Path(__file__).parent / "fixtures"
HOME = FIXTURES / "moscow_cinema_home.html"
DETAIL = FIXTURES / "moscow_cinema_detail.html"

# The fixture was captured on 2026-08-18; the date strip runs 18.08–24.08.
TODAY = dt.date(2026, 8, 18)


def _events():
    return parse_schedule(HOME.read_text(), today=TODAY)


def test_parses_many_film_day_events():
    # 17 films × the published days → dozens of (film, day) rows.
    events = _events()
    assert len(events) >= 40


def test_events_have_dates_titles_urls_and_film_category():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("https://www.moscowcinema.com/en/")
        assert ev.category_slugs == ["film"]


def test_one_event_per_film_per_day_with_all_sessions():
    # Film-scraper shape: one row per (film, day), all sessions in start_times,
    # start_time the earliest. The fixture's tables carry 108 session rows, 22 of
    # which are hall-parallel duplicates of the same wall-clock time (Blue Hall +
    # VIP screening simultaneously) → 86 distinct (film, day, time) sessions.
    events = _events()
    assert all(ev.start_times for ev in events)
    assert all(ev.start_time == min(ev.start_times) for ev in events)
    assert sum(len(ev.start_times) for ev in events) == 86


def test_dates_resolve_within_the_strip_window():
    # The strip is year-less DD.MM; resolved relative to `today` it must land in
    # today…today+6.
    for ev in _events():
        assert TODAY <= ev.start_date <= TODAY + dt.timedelta(days=6)


def test_per_day_session_counts_match_the_fixture_tables():
    # The collapse check at parser level: per-day session totals equal the raw
    # table row counts minus only hall-parallel same-time duplicates (fixture
    # rows per day: 12/30/31/32/2/1, of which 2/6/7/7/0/0 are a second hall
    # screening the same film at the same minute).
    by_day = {}
    for ev in _events():
        by_day[ev.start_date] = by_day.get(ev.start_date, 0) + len(ev.start_times)
    assert by_day == {
        dt.date(2026, 8, 18): 10,
        dt.date(2026, 8, 19): 24,
        dt.date(2026, 8, 20): 24,
        dt.date(2026, 8, 21): 25,
        dt.date(2026, 8, 22): 2,
        dt.date(2026, 8, 23): 1,
    }


def test_external_id_is_slug_at_date_and_unique():
    events = _events()
    ids = [ev.external_id for ev in events]
    assert all(ids)
    assert len(ids) == len(set(ids)), "external_id collapsed film-day occurrences"
    for ev in events:
        slug, _, date_part = ev.external_id.partition("@")
        assert ev.source_url.endswith(f"/{slug}")
        assert date_part == ev.start_date.isoformat()


def test_price_coverage_and_verbatim_amd():
    # Every schedule row carries an AMD price; every event must have one, in the
    # site's own "N ֏" notation (single value or a ≥2× range).
    events = _events()
    assert all(ev.price for ev in events)
    assert all(ev.price.endswith("֏") for ev in events)


def test_language_coverage_is_verbatim_not_inferred():
    # Every row states a display language; kept exactly as written (modulo the
    # site's own trailing-comma noise).
    events = _events()
    assert all(ev.language for ev in events)
    langs = {ev.language for ev in events}
    assert "In Armenian" in langs
    assert "In Russian with Armenian subtitles" in langs
    # The dangling comma the site renders on the multi-language label is trimmed.
    assert "French, Armenian, English, subtitles: Armenian" in langs
    assert not any(ev.language.endswith(",") for ev in events)


def test_hall_names_become_annotations():
    events = _events()
    halls = {a for ev in events for a in ev.annotations}
    assert {"Red Hall", "Blue Hall", "VIP"} <= halls


def test_format_price_collapses_tiers_per_convention():
    assert _format_price([]) is None
    assert _format_price(["2000 ֏", "2000 ֏"]) == "2000 ֏"
    # minor spread (hi < 2×lo) → single highest
    assert _format_price(["2000 ֏", "2500 ֏"]) == "2500 ֏"
    # real spread (hi ≥ 2×lo, e.g. regular vs VIP) → range
    assert _format_price(["2000 ֏", "5000 ֏"]) == "2000–5000 ֏"


def test_parse_film_detail_extracts_synopsis_poster_genre():
    detail = parse_film_detail(DETAIL.read_text())
    assert detail["description"] and "psychological thriller" in detail["description"]
    assert detail["image_url"].startswith("https://moscowcinema.com/storage/")
    assert detail["genre"] == "Psychological thriller"
