"""National Theatre: the date-picker API joined to the production pages
(fixtures captured 2026-10-25)."""

import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers import national_theatre as nt

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name):
    return (FIXTURES / name).read_text()


TODAY = dt.date(2026, 10, 25)


def _events():
    perfs, rooms = nt.picker_performances(json.loads(_read("national_theatre_picker_95888.json")), TODAY)
    pages = [nt.parse_production(_read(f"national_theatre_{s}.html"), f"{nt.SITE}/productions/{s}/")
             for s in ("cloud-9", "hadestown")]
    return perfs, nt.build(perfs, pages, rooms)


def test_listing_links_production_pages_only():
    links = nt.listing_links(_read("national_theatre_listing.html"))
    assert f"{nt.SITE}/productions/cloud-9/" in links
    assert all("/productions/" in u for u in links)


def test_picker_performances():
    perfs, rooms = nt.picker_performances(json.loads(_read("national_theatre_picker_95888.json")), TODAY)
    assert perfs and all(p.production_id == "95888" for p in perfs)
    first = perfs[0]
    # TNEW ids; "…Z" times → London wall time.
    assert (first.performance_id, first.start) == ("95986", dt.datetime(2026, 11, 2, 19, 30))
    assert first.url == "https://tickets.nationaltheatre.org.uk/95888/95986"
    assert set(rooms.values()) == {"Lyttelton Theatre"}
    assert [p.performance_id for p in perfs if p.sold_out] == ["95993"]  # the picker's "soldout"
    assert len({p.performance_id for p in perfs}) == len(perfs)


def test_keeps_auditorium_performances():
    perfs, events = _events()
    assert {e.title for e in events} == {"Cloud 9"}
    assert len(events) == len(perfs)
    assert all(e.annotations == ["Lyttelton"] and e.category_slugs == ["theater"] for e in events)
    assert len({e.external_id for e in events}) == len(events)


def test_price_ladder_and_sold_out():
    _perfs, events = _events()
    assert {e.price for e in events} <= {"£20–105", "sold-out"}
    assert any(e.price == "£20–105" for e in events)


def test_west_end_transfer_is_located_elsewhere():
    page = nt.parse_production(_read("national_theatre_hadestown.html"), f"{nt.SITE}/productions/hadestown/")
    assert page.location == "Lyric Theatre" and page.location not in nt.AUDITORIUMS
    assert page.productions == set()
