import datetime as dt
from pathlib import Path

from cartelera.scrapers.casa_batllo import parse_agenda, parse_artist_events

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA = FIXTURES / "casa_batllo_agenda.html"
ARTIST = FIXTURES / "casa_batllo_artist.html"  # Audrey's page (captured 2026-06-02)

# The fixtures were captured 2026-06-02; the concerts run Jun–Aug 2026. We pin
# `today` so the weekday→year resolution is deterministic offline.
TODAY = dt.date(2026, 6, 2)


def _audrey_events():
    return parse_artist_events(
        ARTIST.read_text(),
        artist_name="Audrey",
        genre="Jazz, Soul, R&B, Disco",
        source_url="https://www.casabatllo.es/en/visit-magic-nights/audrey/",
        today=TODAY,
    )


# --- roster (agenda page) ----------------------------------------------------

def test_agenda_lists_many_artists():
    artists = parse_agenda(AGENDA.read_text())
    assert len(artists) >= 15


def test_agenda_artists_have_name_genre_and_url():
    for name, genre, url in parse_agenda(AGENDA.read_text()):
        assert name
        assert genre  # the roster always carries a genre string
        assert url.startswith("https://www.casabatllo.es/")


def test_agenda_urls_unique():
    artists = parse_agenda(AGENDA.read_text())
    urls = [u for _, _, u in artists]
    assert len(urls) == len(set(urls))


def test_agenda_includes_known_artist_with_genre():
    artists = parse_agenda(AGENDA.read_text())
    audrey = next((a for a in artists if a[0] == "Audrey"), None)
    assert audrey is not None
    assert "Jazz" in audrey[1]


# --- artist page (occurrences) ----------------------------------------------

def test_artist_page_parses_several_occurrences():
    events = _audrey_events()
    assert len(events) >= 4


def test_every_occurrence_has_date_title_url_and_jazz_category():
    for ev in _audrey_events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title == "Audrey"
        assert ev.source_url == "https://www.casabatllo.es/en/visit-magic-nights/audrey/"
        # Contemporary/world live music mapped to the nearest existing music
        # category; never classical, never anything but a single known slug.
        assert ev.category_slugs == ["jazz"]


def test_dates_are_in_the_future_window():
    for ev in _audrey_events():
        assert dt.date(2026, 6, 1) <= ev.start_date <= dt.date(2026, 12, 31)


def test_weekday_year_resolution_is_correct():
    # "Tuesday 9" June must resolve to 2026-06-09, which IS a Tuesday.
    ev = next(e for e in _audrey_events() if e.start_date == dt.date(2026, 6, 9))
    assert ev.start_date.weekday() == 1  # Tuesday
    assert ev.start_time == dt.time(20, 0)


def test_every_occurrence_has_a_showtime():
    # `.event-datetime__hour` ("20:00 h") is present on every bookable concert.
    for ev in _audrey_events():
        assert ev.start_time is not None
        assert isinstance(ev.start_time, dt.time)


def test_price_is_none_no_public_flat_price():
    # No scrape-able flat price (visit+concert bundle; only a residents discount
    # is shown) → None, not guessed.
    for ev in _audrey_events():
        assert ev.price is None


def test_genre_captured_as_annotation_without_leaking_into_category():
    for ev in _audrey_events():
        assert "Jazz, Soul, R&B, Disco" in ev.annotations
        assert ev.category_slugs == ["jazz"]


def test_external_id_is_event_id_and_unique_per_occurrence():
    events = _audrey_events()
    ids = [ev.external_id for ev in events]
    assert all(eid and eid.isdigit() for eid in ids)  # the numeric event_id
    assert len(ids) == len(set(ids))


def test_disabled_past_dates_are_skipped():
    # The "disable" items (past dates with no ticket link / event_id) must not
    # produce events: every emitted event carries a real event_id.
    for ev in _audrey_events():
        assert ev.external_id is not None
