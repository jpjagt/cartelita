import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers.cines_verdi import (
    parse_cartelera,
    parse_film_events,
    _format_price,
    FilmStub,
)

FIXTURES = Path(__file__).parent / "fixtures"
CARTELERA = FIXTURES / "cines_verdi_agenda.html"
FILM_JSON = FIXTURES / "cines_verdi_film_tt33071426.json"  # "The Drama", 15 performances


def _stubs():
    return parse_cartelera(CARTELERA.read_text())


def _film_events():
    """Events parsed from the one saved API fixture, paired with its stub."""
    api = json.loads(FILM_JSON.read_text())
    stub = next(s for s in _stubs() if s.imdbid == "tt33071426")
    return parse_film_events(stub, api)


# ---- cartelera (stub list) ----------------------------------------------------


def test_parses_many_film_stubs():
    stubs = _stubs()
    assert len(stubs) >= 20  # ~35 films in the fixture


def test_stubs_have_imdbid_slug_title():
    for s in _stubs():
        assert s.imdbid.startswith("tt")
        assert s.title
        assert s.source_url.startswith("https://barcelona.cines-verdi.com/")


def test_stub_imdbids_are_unique():
    ids = [s.imdbid for s in _stubs()]
    assert len(ids) == len(set(ids))


def test_known_film_stub_present():
    s = next(s for s in _stubs() if s.imdbid == "tt33071426")
    # The stub title is the page-locale (es) display title, not the API's name.
    assert s.title == "El Drama"
    assert s.source_url == "https://barcelona.cines-verdi.com/el-drama"
    assert s.image_url and s.image_url.startswith("http")


# ---- per-film events (from JSON API) -----------------------------------------


def test_film_parses_all_performances():
    # The fixture film has 15 performances across versions/halls.
    assert len(_film_events()) == 15


def test_every_event_has_date_title_url_and_film_category():
    for ev in _film_events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title == "El Drama"  # stub (es) display title preferred over API name
        assert ev.source_url.startswith("https://barcelona.cines-verdi.com/")
        assert ev.category_slugs == ["film"]


def test_every_event_has_a_showtime():
    for ev in _film_events():
        assert isinstance(ev.start_time, dt.time)


def test_price_coverage_and_format():
    events = _film_events()
    priced = [e for e in events if e.price]
    # Every performance in the fixture carries ticket prices.
    assert len(priced) == len(events)
    for ev in priced:
        assert ev.price.endswith("€")
        # Display string, never a bare number / never the raw cents.
        assert "€" in ev.price and not ev.price.startswith("0")


def test_external_id_is_unique_per_occurrence():
    # performance.id is globally unique per screening; the upsert dedups on it.
    ids = [e.external_id for e in _film_events()]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_hall_captured_as_annotation():
    events = _film_events()
    halls = {a for e in events for a in e.annotations}
    # Verdi + Verdi Park halls both appear in the fixture.
    assert any("V.Park" in h for h in halls)
    assert any(h.startswith("Sala ") for h in halls)


def test_dates_are_consecutive_calendar_days():
    # Sanity: every event's date is a real date within a plausible window.
    for ev in _film_events():
        assert dt.date(2026, 5, 1) <= ev.start_date <= dt.date(2026, 12, 31)


# ---- price formatting --------------------------------------------------------


def test_format_price_takes_max_and_formats_spanish():
    assert _format_price(["600", "750", "650"]) == "7,50€"
    assert _format_price(["600", "600"]) == "6€"
    assert _format_price(["540"]) == "5,40€"
    assert _format_price([]) is None
    assert _format_price(None) is None


def test_film_with_no_title_yields_nothing():
    # Defensive: a stub with no title and a result with no name produces nothing.
    stub = FilmStub("ttX", "/x", title=None, image_url=None)
    assert parse_film_events(stub, {"result": {"name": "", "events": []}}) == []
