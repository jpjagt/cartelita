import datetime as dt
from pathlib import Path

from cartelera.scrapers.santa_maria_del_mar import parse_agenda, parse_detail

FIXTURE = Path(__file__).parent / "fixtures" / "santa_maria_del_mar_agenda.html"
DETAIL_FIXTURE = Path(__file__).parent / "fixtures" / "santa_maria_del_mar_detail.html"


def _events():
    return parse_agenda(FIXTURE.read_text())


def test_parses_concerts():
    # The first agenda page lists 10 posts; 8 are concerts (2 are parish retreats
    # that must be filtered out).
    events = _events()
    assert len(events) == 8


def test_non_concert_parish_posts_are_filtered_out():
    titles = [e.title.lower() for e in _events()]
    # "Recés de Quaresma" / "Recés d'Advent" are retreats, not concerts.
    assert not any("recés" in t or "reces" in t for t in titles)


def test_events_have_dates_titles_urls_and_classical_category():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("https://www.santamariadelmar.barcelona/ca/")
        # Single-category venue: every concert is classical.
        assert ev.category_slugs == ["classical"]


def test_list_has_no_time_or_price():
    # Time and price live only on the detail page; the list parser leaves them unset.
    for ev in _events():
        assert ev.start_time is None
        assert ev.price is None


def test_image_urls_are_absolute_https():
    # The agenda card carries a structured-data image for each post.
    with_image = [e for e in _events() if e.image_url]
    assert with_image
    for ev in with_image:
        assert ev.image_url.startswith("https://www.santamariadelmar.barcelona/")


def test_cycle_captured_as_annotation_not_category():
    events = _events()
    # The "L'Orgue del Mar" cycle is captured as a free-form annotation.
    organ = next(e for e in events if "Orgue del Mar" in e.title)
    assert any("Orgue del Mar" in a for a in organ.annotations)
    # ...and never leaks into category_slugs.
    assert organ.category_slugs == ["classical"]


def test_external_id_is_unique_per_occurrence():
    ids = [e.external_id for e in _events()]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_external_id_encodes_slug_and_date():
    ev = next(e for e in _events() if "joan-segui" in e.source_url)
    assert ev.external_id == "concert-de-joan-segui-cicle-l-orgue-del-mar-de-2026@2026-02-20"
    assert ev.start_date == dt.date(2026, 2, 20)


def test_choral_work_with_missa_in_title_is_kept():
    # "El Cant de la Sibil·la i Missa del Gall" contains "missa" but is a choral
    # concert — the sibil·la keyword keeps it.
    titles = [e.title for e in _events()]
    assert any("Cant de la Sibil" in t for t in titles)


def test_parse_detail_extracts_time_and_main_price():
    # Joan Seguí detail page: "Hora: 20:30h", "Entrada: 9€" (reduced 7€ is skipped).
    start_time, price = parse_detail(DETAIL_FIXTURE.read_text())
    assert start_time == dt.time(20, 30)
    assert price == "9€"
