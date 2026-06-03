import datetime as dt
from pathlib import Path

from cartelera.scrapers.cinema_malda import (
    parse_agenda,
    parse_prices,
    slugify_title,
    _build_home_index,
)

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA = FIXTURES / "cinema_malda_agenda.html"
HOME = FIXTURES / "cinema_malda_home.html"
PRICES = FIXTURES / "cinema_malda_precios.html"


def _home():
    return _build_home_index(HOME.read_text())


def _prices():
    return parse_prices(PRICES.read_text())


def _events():
    slugs, images, titles = _home()
    return parse_agenda(
        AGENDA.read_text(),
        slugs=slugs,
        images=images,
        prices=_prices(),
        titles=titles,
    )


def test_parses_several_screenings():
    # The fixture week (Tue–Thu, 2026-06-02..04) has multiple screenings/day.
    events = _events()
    assert len(events) >= 8


def test_events_have_dates_titles_urls_and_film_category():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("https://www.cinemamalda.com/")
        # Single-category venue: every session is film.
        assert ev.category_slugs == ["film"]


def test_every_event_has_a_showtime():
    for ev in _events():
        assert isinstance(ev.start_time, dt.time)


def test_dates_fall_in_the_fixture_week():
    # Fixture header: "DEL 29 AL 4 DE JUNIO DE 2026"; sessions run Tue 2 → Thu 4.
    for ev in _events():
        assert dt.date(2026, 6, 1) <= ev.start_date <= dt.date(2026, 6, 7)


def test_source_urls_resolve_to_film_detail_pages():
    # With the homepage slug set, titles resolve to real /<slug>/ detail pages
    # rather than falling back to the day-by-day page for most screenings.
    events = _events()
    detail = [
        e for e in events
        if e.source_url != "https://www.cinemamalda.com/cartelera-dia-dia/"
    ]
    assert len(detail) >= len(events) * 0.9
    for ev in detail:
        # /slug/ shape
        tail = ev.source_url.rstrip("/").rsplit("/", 1)[-1]
        assert tail and tail != "cinemamalda.com"


def test_price_coverage():
    # Every screening gets the venue's per-weekday general price.
    events = _events()
    priced = [e for e in events if e.price]
    assert len(priced) >= len(events) * 0.9
    for ev in priced:
        assert ev.price.endswith("€")


def test_prices_parsed_per_weekday():
    p = _prices()
    # Mon/Wed día del espectador 5,90€; Tue/Thu/Fri 7,50€; Sat 9€.
    assert p[0] == "5,90€"  # Monday
    assert p[2] == "5,90€"  # Wednesday
    assert p[1] == "7,50€"  # Tuesday
    assert p[3] == "7,50€"  # Thursday
    assert p[5] == "9€"     # Saturday


def test_vo_tag_captured_as_annotation():
    events = _events()
    annotated = [e for e in events if e.annotations]
    # Nearly every Cinema Maldà title carries an original-version (VO*) tag.
    assert len(annotated) >= len(events) * 0.9
    tags = {a for e in events for a in e.annotations}
    assert any(t.startswith("VO") for t in tags)
    # The VO tag must not leak into the title.
    for ev in events:
        assert "(VO" not in ev.title.upper()


def test_external_id_is_unique_per_occurrence():
    # The same film screens on several days (e.g. "El drama", "Conoce a los
    # bárbaros"); external_id must distinguish the occurrences (upsert dedups on
    # it), so all ids are unique within the batch.
    events = _events()
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))


def test_external_id_encodes_slug_and_occurrence():
    events = _events()
    ev = next(e for e in events if e.start_time == dt.time(16, 15)
              and e.start_date == dt.date(2026, 6, 2))
    assert ev.title == "Tres adioses"
    assert ev.external_id == "tres-adioses@2026-06-02T1615"
    assert ev.source_url == "https://www.cinemamalda.com/tres-adioses/"


def test_recurring_film_distinct_occurrences():
    # "Conoce a los bárbaros" screens Tue/Wed/Thu — three distinct events sharing
    # the slug but with distinct external_ids.
    events = _events()
    barbaros = [e for e in events if e.source_url.endswith("/conoce-a-los-barbaros/")]
    assert len(barbaros) >= 3
    assert len({e.external_id for e in barbaros}) == len(barbaros)
    assert len({e.start_date for e in barbaros}) == len(barbaros)


def test_slugify_drops_parentheticals():
    assert slugify_title("UYARIY (ESCUCHAR) (VOE) (ESTRENO)") == "uyariy"
    assert slugify_title("EL DRAMA (VOSE)") == "el-drama"
    assert slugify_title("Conoce a los bárbaros (VOSE)") == "conoce-a-los-barbaros"
