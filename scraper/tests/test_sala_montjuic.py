import datetime as dt
from pathlib import Path

from cartelera.scrapers.sala_montjuic import parse_agenda, parse_film_time

FIXTURE = Path(__file__).parent / "fixtures" / "sala_montjuic_agenda.html"
MOVIE_FIXTURE = Path(__file__).parent / "fixtures" / "sala_montjuic_movie.html"

# The 2026 programme (the saved fixture) runs 10 Jul → 5 Aug 2026. Anchor the
# year-inference to a date inside that season so the offline tests are stable.
TODAY = dt.date(2026, 7, 1)


def _events():
    return parse_agenda(FIXTURE.read_text(), today=TODAY)


def test_parser_returns_a_list_even_for_an_empty_page():
    # SEASONAL: outside summer the programme may be empty/unpublished. The parser
    # must still run and return a list (possibly empty) without error.
    out = parse_agenda("<html><body>No programme yet</body></html>", today=TODAY)
    assert isinstance(out, list)
    assert out == []


def test_parses_the_published_season():
    # The 2026 fixture has 16 screenings.
    events = _events()
    assert len(events) >= 10


def test_events_have_dates_titles_urls_and_film_category():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("https://www.salamontjuic.org/movie/")
        # Single-category venue: every screening is film.
        assert ev.category_slugs == ["film"]


def test_dates_fall_in_the_summer_season():
    # Open-air summer series: 2026 edition is 10 Jul → 5 Aug.
    for ev in _events():
        assert dt.date(2026, 7, 10) <= ev.start_date <= dt.date(2026, 8, 5)


def test_external_id_is_unique_per_occurrence():
    events = _events()
    ids = [e.external_id for e in events]
    assert all(ids)
    assert len(ids) == len(set(ids))
    # slug qualified by the occurrence date.
    ev = next(e for e in events if e.source_url.endswith("/movie/flores-para-antonio/"))
    assert ev.external_id == "flores-para-antonio@2026-07-10"


def test_sold_out_normalized_as_price():
    events = _events()
    by_url = {e.source_url: e for e in events}
    # MARTY SUPREME and HAMNET carry a SOLD OUT meta in the fixture.
    assert by_url["https://www.salamontjuic.org/movie/marty-supreme/"].price == "sold-out"
    assert by_url["https://www.salamontjuic.org/movie/hamnet/"].price == "sold-out"
    # A non-sold-out screening has no price (tickets are sold off-site).
    assert by_url["https://www.salamontjuic.org/movie/flores-para-antonio/"].price is None


def test_live_music_act_captured_as_annotation():
    events = _events()
    # Almost every night has a live-music opener captured as an annotation.
    annotated = [e for e in events if e.annotations]
    assert len(annotated) >= len(events) * 0.9
    ev = next(e for e in events if e.source_url.endswith("/movie/flores-para-antonio/"))
    assert ev.annotations == ["Acorde a Ti"]
    # The SOLD OUT flag must NOT leak into annotations.
    for e in events:
        assert all("sold out" not in a.lower() for a in e.annotations)


def test_images_present_and_absolute():
    for ev in _events():
        assert ev.image_url and ev.image_url.startswith("https://www.salamontjuic.org/")


def test_film_time_parsed_from_detail_page():
    # The detail page schedules the film at "22:00 – PEL·LÍCULA" (not the
    # "20:45 – CONCERT" opener).
    assert parse_film_time(MOVIE_FIXTURE.read_text()) == dt.time(22, 0)


def test_times_applied_when_supplied():
    url = "https://www.salamontjuic.org/movie/flores-para-antonio/"
    events = parse_agenda(FIXTURE.read_text(), today=TODAY, times={url: dt.time(22, 0)})
    ev = next(e for e in events if e.source_url == url)
    assert ev.start_time == dt.time(22, 0)


def test_no_time_when_not_supplied():
    # Offline parse without detail fetches: start_time is None.
    for ev in _events():
        assert ev.start_time is None


def test_known_screening_present_with_right_fields():
    events = _events()
    ev = next(e for e in events if e.source_url.endswith("/movie/the-royal-tenenbaums/"))
    assert ev.title == "THE ROYAL TENENBAUMS"
    assert ev.start_date == dt.date(2026, 8, 3)
    assert ev.annotations == ["Sara Aldana"]
