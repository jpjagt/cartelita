import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers import _aecid
from cartelera.scrapers.cce_asuncion import CONFIG, SITE_URL

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 14)


def _items() -> list[dict]:
    pages = json.loads((FIXTURES / "cce_asuncion_listing.json").read_text())
    return [i for p in pages for i in _aecid.parse_listing(p, SITE_URL)]


def _detail(slug: str) -> _aecid.Detail:
    html = (FIXTURES / f"cce_asuncion_detail_{slug}.html").read_text()
    return _aecid.parse_detail(html, SITE_URL)


def _events(slug: str, today: dt.date = TODAY):
    d = _detail(slug)
    item = {"url": f"{SITE_URL}/w/{slug}", "article_id": "A1", "title": d.title,
            "categories": d.categories}
    return _aecid.events_from_detail(d, item, CONFIG, today)


def test_listing_endpoint_from_search_page():
    url, ns = _aecid.listing_endpoint((FIXTURES / "cce_asuncion_search.html").read_text())
    assert url.startswith(f"{SITE_URL}/eventos/buscador-de-eventos?p_p_id=")
    assert "p_p_resource_id=listadoEventos" in url
    assert ns == "_es_aecid_agenda_eventos_AgendaEventosPortlet_INSTANCE_vBvwgYvFXCzo_"
    page = _aecid.listing_page_url(url, ns, 12, TODAY)
    assert f"{ns}start=12" in page and f"{ns}from=2026-10-14" in page and f"{ns}sort=asc" in page


def test_listing_cards():
    items = _items()
    assert len(items) == 15  # totalHits on 2026-10-14, two pages
    assert all(i["url"].startswith(f"{SITE_URL}/w/") and i["article_id"] for i in items)
    cine = next(i for i in items if i["title"] == "Octubre de cine español")
    assert cine["categories"] == ["Cine / Audiovisual"]
    assert cine["article_id"] == "13451989"


def test_only_programme_cards_qualify():
    kept = [i["title"] for i in _items() if _aecid.categorize(i["categories"], CONFIG)]
    # Exhibitions, reading clubs, workshops ("Formación"), community items: out.
    assert kept == ["Octubre de cine español"]


def test_detail_fields():
    d = _detail("arquetipos-en-el-cine")
    assert d.categories == ["Formación", "Cine / Audiovisual"]  # one dd per label
    assert len(d.dates) == 6  # hidden ("Mostrar más") dates included
    assert d.horario == "18.00 a 20.30 horas."
    assert _events("arquetipos-en-el-cine") == []  # a workshop


def test_film_cycle_times_from_the_body_per_date():
    events = _events("octubre-de-cine-espanol")
    # 5 Oct (Cine de Barrio, Día del Cine Español) is past on 14 Oct.
    assert [(e.start_date, e.start_time) for e in events] == [
        (dt.date(2026, 10, 28), dt.time(19, 30)),
        (dt.date(2026, 10, 29), dt.time(19, 30)),
        (dt.date(2026, 10, 30), dt.time(19, 30)),
        (dt.date(2026, 10, 31), dt.time(18, 0)),
        (dt.date(2026, 10, 31), dt.time(20, 0)),
    ]
    for e in events:
        assert e.title == "Octubre de cine español"
        assert e.category_slugs == ["film"]
        assert e.price == "free"  # "acceso libre y gratuito hasta completar aforo"
        assert e.source_url == f"{SITE_URL}/w/octubre-de-cine-espanol"
        assert e.image_url and e.image_url.startswith(SITE_URL + "/documents/")
        assert e.description
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))
    assert ids[0] == "A1@2026-10-28T1930"


def test_horario_field_gives_the_time():
    (ev,) = _events("leira", today=dt.date(2026, 1, 1))
    assert (ev.start_date, ev.start_time) == (dt.date(2026, 4, 21), dt.time(19, 30))
    assert ev.category_slugs == ["theater"]
    assert ev.annotations == ["Nova galega de danza"]  # the subtitle


def test_dates_without_a_stated_time_have_none():
    events = _events("ciclo-de-cine-europeo-2026", today=dt.date(2026, 1, 1))
    assert len(events) == 10
    assert events[0].start_time == dt.time(19, 30)  # "19 de agosto ... 19:30 h"
    assert all(e.start_time is None for e in events[1:])


def test_place_filter():
    assert _aecid.at_own_place("Centro Cultural de España en Asunción y Luque", CONFIG)
    assert _aecid.at_own_place("", CONFIG)
    assert not _aecid.at_own_place("Sala La Correa", CONFIG)
    assert not _aecid.at_own_place("Casa Bicentenario de las Artes Visuales", CONFIG)


def test_categorize_adds_kids_only_to_programme():
    assert _aecid.categorize(["Escénicas", "Infantil / Juvenil"], CONFIG) == ["theater", "kids"]
    assert _aecid.categorize(["Letras", "Infantil / Juvenil"], CONFIG) == []
    assert _aecid.categorize(["Formación", "Escénicas"], CONFIG) == []


def test_price_from_body():
    assert _aecid.price("Entrada: Gs. 50.000. Reservas al ...") == "50.000₲"
    assert _aecid.price("con acceso libre y gratuito hasta completar aforo") == "free"
    assert _aecid.price("Entrada libre.") == "free"
    assert _aecid.price("La participación es gratuita, mediante selección") is None
    assert _aecid.price("") is None


def test_spanish_dates():
    assert _aecid.parse_date("05/Oct/2026") == dt.date(2026, 10, 5)
    assert _aecid.parse_date("08/Ago/2026") == dt.date(2026, 8, 8)
    assert _aecid.parse_date("31/Dic/2026") == dt.date(2026, 12, 31)
    assert _aecid.parse_date("Según programación") is None
