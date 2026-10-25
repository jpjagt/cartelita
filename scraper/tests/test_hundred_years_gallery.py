"""Offline tests for the Hundred Years Gallery scraper (saved fixtures)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from cartelera.scrapers import load_all
from cartelera.scrapers.hundred_years_gallery import (
    VENUE_SLUG,
    build_event,
    is_kept_type,
    item_type,
    parse_post,
    parse_upcoming,
    resolve_date,
)

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 24)


def _items():
    return parse_upcoming((FIXTURES / "hundred_years_gallery_upcoming.html").read_text(), TODAY)


def _post(slug: str) -> dict:
    return parse_post((FIXTURES / f"hundred_years_gallery_{slug}.html").read_text())


def test_type_prefix_curation():
    assert is_kept_type(item_type("Music : A Bigger Mouth. Wednesday 11th November 19:00"))
    assert is_kept_type(item_type("Music: Sofia Vaisman-Maturana. Saturday 12th December 19:30"))
    assert is_kept_type(item_type("Music / Poetry : Unhomed. Saturday 14th November 20:00"))
    assert is_kept_type(item_type("Residency : Mark Wastell. Saturday 31st October 16:00"))
    assert not is_kept_type(item_type("Exhibition : Darkness Never Lasts. 7th October to 1st November 2026"))
    assert not is_kept_type(item_type("Books : VI Festival. Friday 13th November 19:30"))
    assert not is_kept_type(item_type("Performance : DREAM. Friday 6th November 19:00"))
    assert not is_kept_type(item_type("Dissidences 7. Sound, voice, word. Saturday 14th November 4.30"))


def test_upcoming_items():
    items = _items()
    assert len(items) == 17
    types = {i["type"] for i in items}
    assert types <= {"Music", "Residency", "Music / Poetry"}
    knot = next(i for i in items if i["title"].startswith("KNOT #14"))
    assert knot["title"] == "KNOT #14 : Xiang / Fabian Neubauer / Yoni Silver / Zheng Hao"
    assert knot["start_date"] == dt.date(2026, 11, 7) and knot["start_time"] == dt.time(19, 30)
    loose = next(i for i in items if i["title"].startswith("Loose Fittings"))
    assert loose["start_time"] == dt.time(15, 0)  # "15.00"
    # December items stay in 2026; the year comes from the weekday.
    rick = next(i for i in items if i["title"] == "Rick Jensen Trio")
    assert rick["start_date"] == dt.date(2026, 12, 11)


def test_year_rollover_by_weekday():
    assert resolve_date(8, 1, "Friday", dt.date(2026, 12, 20)) == dt.date(2027, 1, 8)


def test_post_price_description_image():
    b = _post("music-bismillah-cest-les-tenebres")
    assert b["price"] == "£10"
    assert "Pascal Marzan" in b["description"]
    w = _post("residency-mark-wastell-duo-intern-with-charlotte-keeffe")
    assert w["price"] == "free"  # "Free event. Spectators welcome."
    d = _post("residency-collective-drawing-october")
    assert d["price"] == "free"  # "free entry, donations welcome"
    k = _post("music-knot-14")
    assert k["price"] is None and k["image_url"].endswith("knot14-02.jpg")


def test_build_event():
    item = next(i for i in _items() if i["title"].startswith("Bismillah"))
    ev = build_event(item, _post("music-bismillah-cest-les-tenebres"))
    assert ev.category_slugs == ["alternative"]
    assert ev.source_url == "http://hundredyearsgallery.co.uk/music-bismillah-cest-les-tenebres/"
    assert ev.external_id == "music-bismillah-cest-les-tenebres"
    assert ev.start_date == dt.date(2026, 10, 29) and ev.start_time == dt.time(19, 30)
    assert ev.price == "£10" and ev.annotations == ["Music"]


def test_registered():
    _scraper, source = load_all()[VENUE_SLUG]
    (venue,) = source.venues
    assert venue.city_slug == "london" and venue.category_slugs == ["alternative"]
