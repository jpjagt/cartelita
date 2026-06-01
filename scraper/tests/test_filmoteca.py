import datetime as dt
from pathlib import Path
from cartelera.scrapers.filmoteca import parse_agenda, parse_standard_price

FIXTURE = Path(__file__).parent / "fixtures" / "filmoteca_agenda.html"
INFO_FIXTURE = Path(__file__).parent / "fixtures" / "filmoteca_info.html"


def _events():
    return parse_agenda(FIXTURE.read_text())


def test_parses_many_events():
    # The fixture is one week (Tue–Sun, closed Mondays) with several screenings/day.
    events = _events()
    assert len(events) >= 20


def test_events_have_dates_titles_urls_and_film_category():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("https://www.filmoteca.cat/web/ca/film/")
        # Single-category venue: every screening is film.
        assert ev.category_slugs == ["film"]


def test_dates_fall_in_the_fixture_week():
    # Fixture is the week of 2026-05-25 (Mon); screenings run Tue 26 → Sun 31.
    for ev in _events():
        assert dt.date(2026, 5, 26) <= ev.start_date <= dt.date(2026, 5, 31)


def test_every_event_has_a_showtime():
    # The card's `.hour` is always present — it's the local wall-clock time.
    events = _events()
    for ev in events:
        assert ev.start_time is not None
        assert isinstance(ev.start_time, dt.time)


def test_no_price_on_cards_themselves():
    # The screening cards carry no price; without a default supplied, price is None.
    for ev in _events():
        assert ev.price is None


def test_standard_price_parsed_from_info_page():
    # "Entrada individual* — 4 €" is the standard single-ticket rate.
    assert parse_standard_price(INFO_FIXTURE.read_text()) == "4€"


def test_default_price_applied_to_every_event():
    # The standard price (read once from the info page) is applied to all events,
    # as free text with the € sign (never parsed to a number).
    events = parse_agenda(FIXTURE.read_text(), default_price="4€")
    assert events
    for ev in events:
        assert ev.price == "4€"


def test_cycle_captured_as_annotation():
    events = _events()
    annotated = [e for e in events if e.annotations]
    # Nearly every screening belongs to a programming cycle (cicle).
    assert len(annotated) >= len(events) * 0.9
    # A known cycle from the fixture week.
    cycles = {a for e in events for a in e.annotations}
    assert "JAPANIMERAMA" in cycles


def test_external_id_and_image_present():
    for ev in _events():
        assert ev.external_id  # film slug qualified by occurrence date+time
        assert ev.image_url and ev.image_url.startswith("http")


def test_external_id_is_unique_per_occurrence():
    # The same film screens on several dates/times; external_id must distinguish
    # those occurrences (the upsert dedups on it), so all ids are unique.
    events = _events()
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))


def test_image_urls_are_absolute_and_https_normalized():
    for ev in _events():
        assert ev.image_url.startswith("https://www.filmoteca.cat/")


def test_known_screening_present_with_right_fields():
    # Find by predicate, not by index (fixture data is volatile across weeks).
    events = _events()
    ev = next(e for e in events if e.source_url.endswith("/film/nationalite-immigre-mes-voisins"))
    assert ev.title == "Nationalité: immigré | Mes voisins"
    assert ev.start_date == dt.date(2026, 5, 26)
    assert ev.start_time == dt.time(17, 0)
    assert "Llogateres del món" in ev.annotations


def test_external_id_encodes_film_slug_and_occurrence():
    events = _events()
    ev = next(e for e in events if e.source_url.endswith("/film/nationalite-immigre-mes-voisins"))
    # film slug, qualified by date+time so repeat screenings stay distinct.
    assert ev.external_id == "nationalite-immigre-mes-voisins@2026-05-26T1700"
    assert ev.source_url.endswith("/film/" + ev.external_id.split("@")[0])
