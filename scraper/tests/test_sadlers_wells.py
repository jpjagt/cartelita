"""Sadler's Wells: website what's-on + show pages, TNEW as cross-check
(fixtures captured 2026-10-25)."""

import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers import _tnew as tnew
from cartelera.scrapers import sadlers_wells as sw

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 25)
SHOWS = ["shochiku-kabuki", "motionhouse-hidden", "georgia-tegou-in-the-quiet-of-us", "the-snowman-2026", "culture-club-2026"]


def _read(name):
    return (FIXTURES / name).read_text()


def _events(perfs=True):
    shows, _pages = sw.parse_listing(_read("sadlers_wells_listing.html"))
    pages = {}
    for slug in SHOWS:
        url = f"{sw.SITE}/whats-on/{slug}/"
        shows.setdefault(url, slug)
        pages[url] = sw.parse_show(_read(f"sadlers_wells_{slug}.html"))
    feed = tnew.performances(json.loads(_read("sadlers_wells_tnew.json"))["productions"]) if perfs else []
    return sw.build(shows, pages, feed, TODAY)


def test_listing_gives_titles_and_pagination():
    shows, pages = sw.parse_listing(_read("sadlers_wells_listing.html"))
    assert shows and all(sw.SHOW_LINK.fullmatch(u) for u in shows)
    assert any(" - " in t for t in shows.values())
    assert any("/whats-on/page/2/" in p for p in pages)


def test_stages_split_into_three_buildings():
    by_page = {e.source_url.rstrip("/").rsplit("/", 1)[-1]: e.venue_slug for e in _events()}
    assert by_page["the-snowman-2026"] == "peacock-theatre"
    assert by_page["motionhouse-hidden"] == "sadlers-wells-east"
    assert by_page["georgia-tegou-in-the-quiet-of-us"] == "sadlers-wells"  # Lilian Baylis Studio
    tegou = [e for e in _events() if "tegou" in e.source_url]
    assert all("Lilian Baylis Studio" in e.annotations for e in tegou)


def test_fields_prices_and_ids():
    events = _events()
    assert all(e.category_slugs == ["dance"] for e in events)
    assert len({e.external_id for e in events}) == len(events)
    assert all(e.start_time is not None for e in events)
    snowman = [e for e in events if "snowman" in e.source_url]
    assert {e.price for e in snowman} <= {"from £30", "from £18"}
    assert any("relaxed performance" in e.annotations for e in events if "motionhouse" in e.source_url)


def test_sold_out_performances_without_booking_link_are_kept():
    kabuki = [e for e in _events() if "kabuki" in e.source_url]
    assert [e.start_date for e in kabuki] == [dt.date(2027, 1, 30), dt.date(2027, 1, 31)]
    assert {e.price for e in kabuki} == {"sold-out"}


def test_year_from_weekday_matches_tnew():
    with_tnew = {(e.external_id, e.start_date, e.start_time) for e in _events(perfs=True)}
    without = {(e.external_id, e.start_date, e.start_time) for e in _events(perfs=False)}
    assert with_tnew == without


def test_unknown_stage_is_dropped():
    inst = sw.Instance("1", 4, 30, 10, dt.time(19, 30), "Somewhere Else", "from £10", False, None)
    assert sw.build({"u": "T"}, {"u": [inst]}, [], TODAY) == []
