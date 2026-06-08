import datetime as dt
from pathlib import Path

from cartelera.scrapers.cinemes_girona import parse_agenda

FIXTURE = Path(__file__).parent / "fixtures" / "cinemes_girona_agenda.html"


def _events():
    return parse_agenda(FIXTURE.read_text())


def test_parses_many_events():
    # ~22 films, each with several dated showtimes → many occurrences.
    events = _events()
    assert len(events) >= 50


def test_events_have_dates_titles_urls_and_film_category():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("https://www.cinemesgirona.cat/")
        # Single-category venue: every screening is film.
        assert ev.category_slugs == ["film"]


def test_every_event_has_a_showtime():
    # Showtimes come from the anchor's title / text; an occurrence without a
    # parseable time is not emitted, so every event has one.
    for ev in _events():
        assert ev.start_time is not None
        assert isinstance(ev.start_time, dt.time)


def test_dates_are_in_the_future_window():
    # Fixture captured 2026-06-01; the programme runs from the next day onward.
    events = _events()
    for ev in events:
        assert dt.date(2026, 6, 1) <= ev.start_date <= dt.date(2027, 1, 1)


def test_price_coverage():
    # No per-screening price on the page → a public-price default is applied to
    # every occurrence. This is the coverage test that would catch a silent price
    # drop.
    events = _events()
    priced = [e for e in events if e.price]
    assert len(priced) == len(events)


def test_price_is_weekday_or_weekend_tier_by_date():
    # The 7€/9€ spread is minor (high < 2× low) so we never show a range; instead
    # each occurrence gets the single tier applicable to its date.
    for ev in _events():
        expected = "9€" if ev.start_date.weekday() >= 5 else "7€"
        assert ev.price == expected


def test_price_can_be_cleared():
    events = parse_agenda(FIXTURE.read_text(), price_for_date=lambda _: None)
    assert events
    assert all(e.price is None for e in events)


def test_external_id_is_unique_per_occurrence():
    # The same film screens on several dates/times; the film id alone is shared
    # across them, so external_id must qualify it with date+time. All ids unique.
    events = _events()
    ids = [e.external_id for e in events]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_external_id_encodes_filmid_and_occurrence():
    for ev in _events():
        filmid, _, occ = ev.external_id.partition("@")
        assert filmid.isdigit()
        # occurrence suffix is "<date>T<HHMM>" matching the event's date+time.
        assert occ == f"{ev.start_date.isoformat()}T{ev.start_time.strftime('%H%M')}"


def test_image_urls_are_absolute_https():
    # Posters are hosted off-site (bizcochito.es); whatever the host, absolute.
    for ev in _events():
        if ev.image_url:
            assert ev.image_url.startswith("https://")


def test_genre_and_version_annotations_captured():
    events = _events()
    annotated = [e for e in events if e.annotations]
    # Most films carry a genre and/or a version label.
    assert len(annotated) >= len(events) * 0.8
    labels = {a for e in events for a in e.annotations}
    # Version labels observed on the page.
    assert labels & {"DIG", "VOSE", "CATALÀ", "CASTELLÀ", "VOSI", "VOSC"}


def test_category_slug_never_leaks_a_genre():
    # Genres/versions are annotations, never categories.
    for ev in _events():
        assert ev.category_slugs == ["film"]
        assert "film" not in ev.annotations


def test_known_film_present_with_right_fields():
    # Find by predicate, not index (fixture is volatile across weeks).
    events = _events()
    cowgirl = [e for e in events if e.source_url.endswith("/cowgirl-cat")]
    assert cowgirl
    ev = cowgirl[0]
    assert ev.title == "Cowgirl (CAT)"
    assert ev.start_date == dt.date(2026, 6, 2)
    assert "CATALÀ" in ev.annotations
