import datetime as dt
from pathlib import Path

from cartelera.scrapers.cine_de_barrio import BASE_URL, parse_detail, parse_list

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA = (FIXTURES / "cine_de_barrio_agenda.html").read_text()


def _film(slug: str) -> dict:
    return next(f for f in parse_list(AGENDA) if f["url"].endswith("/" + slug))


def _detail(slug: str):
    html = (FIXTURES / f"cine_de_barrio_detail_{slug}.html").read_text()
    return parse_detail(html, _film(slug))


def test_list_has_one_card_per_film():
    films = parse_list(AGENDA)
    assert len(films) == 9
    assert len({f["url"] for f in films}) == 9
    for f in films:
        assert f["url"].startswith(f"{BASE_URL}/eventos/")
        assert f["title"]
        assert f["image_url"].startswith("https://framerusercontent.com/")


def test_non_ascii_slug_is_percent_encoded():
    urls = [f["url"] for f in parse_list(AGENDA)]
    assert f"{BASE_URL}/eventos/el-pr%C3%ADncipe-de-nanawa" in urls


def test_genre_label_goes_to_annotations():
    assert _film("morgue")["genre"] == "Terror"
    assert _film("narciso")["genre"] == ""


def test_one_event_per_screening_deduped_across_breakpoints():
    events = _detail("narciso")
    # Six showtimes, each rendered twice (two Framer breakpoints).
    assert len(events) == 6
    assert [(e.start_date, e.start_time) for e in events] == [
        (dt.date(2026, 10, 16), dt.time(21, 0)),
        (dt.date(2026, 10, 16), dt.time(19, 0)),
        (dt.date(2026, 10, 23), dt.time(19, 0)),
        (dt.date(2026, 10, 23), dt.time(21, 0)),
        (dt.date(2026, 10, 30), dt.time(19, 0)),
        (dt.date(2026, 10, 30), dt.time(21, 0)),
    ]


def test_fields_and_wall_clock_time():
    events = _detail("psycho")
    assert [(e.start_date, e.start_time) for e in events] == [
        (dt.date(2026, 10, 14), dt.time(19, 0)),
        (dt.date(2026, 10, 14), dt.time(21, 10)),  # the rendered "21:10", not UTC-shifted
    ]
    for ev in events:
        assert ev.title == "Psycho"
        assert ev.category_slugs == ["film"]
        assert ev.price == "40.000₲"
        assert ev.source_url == f"{BASE_URL}/eventos/psycho"
        assert ev.description and ev.description.startswith("Marion Crane")
        assert ev.image_url
        assert ev.language is None


def test_external_id_is_the_screening_record_id():
    ids = [e.external_id for slug in ("narciso", "psycho") for e in _detail(slug)]
    assert len(ids) == len(set(ids)) == 8
    assert all(i.startswith("rec") for i in ids)


def test_free_screening_note_is_free_price():
    (ev,) = _detail("morgue")
    assert (ev.start_date, ev.start_time) == (dt.date(2026, 10, 24), dt.time(17, 0))
    assert ev.price == "free"  # "Entrada libre y gratuita. Por orden de llegada …"
    assert ev.external_id == "morgue@2026-10-24T1700"  # no ticket link → slug@datetime
    assert ev.annotations == ["Terror"]


def test_price_is_read_per_showtime_card():
    html = """
    <div data-framer-name="info"><div data-framer-name="Titulo"><p>Corto</p></div></div>
    <div data-border="true">
      <div data-framer-name="Fecha y Hora"><h4><time datetime="2026-11-02T20:00:00.000Z">2 nov 2026, 20:00</time></h4></div>
      <section><div>Sin precio publicado</div></section>
    </div>
    <div data-border="true">
      <div data-framer-name="Fecha y Hora"><h4><time datetime="2026-11-03T20:00:00.000Z">3 nov 2026, 20:00</time></h4></div>
      <div data-framer-name="Precio"><p>50.000 PYG</p></div>
      <section><a href="https://tally.so/r/x?screening_id=recB&price=50000">Comprar entrada</a></section>
    </div>
    """
    film = {"url": f"{BASE_URL}/eventos/corto", "title": "Corto", "genre": "", "image_url": None}
    a, b = parse_detail(html, film)
    # The first card states no price: it must not borrow the next card's.
    assert (a.price, a.external_id) == (None, "corto@2026-11-02T2000")
    assert (b.price, b.external_id) == ("50.000₲", "recB")
