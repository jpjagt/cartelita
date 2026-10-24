"""Blackheath Halls / Trinity Laban on the shared Spektrix helper, against
saved API responses (captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import blackheath_halls as bh

FIXTURES = Path(__file__).parent / "fixtures"


def _scraped(prices=None):
    events = json.loads((FIXTURES / "blackheath_halls_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "blackheath_halls_spektrix_instances.json").read_text())
    bh.fill_categories(events, instances)
    return bh.build(spk.select(events, instances, bh.categorize, bh.venue), prices or {})


def test_categories_from_the_website_filter_words():
    by_title = {e.title: e.category_slugs for e in _scraped()}
    assert by_title["Lunchtime Recital: Waldstein Trio"] == ["classical"]
    assert by_title["Regents Opera And New Palace Opera: Strauss' Elektra"] == ["classical"]
    assert by_title["Emma Smith"] == ["jazz"]
    assert by_title["The Gruffalo"] == ["kids"]
    assert by_title["Comedy Club 4 Kids"] == ["kids"]
    # Trinity Laban's external concert has no event Category; its
    # performance says "Classical music".
    assert by_title["Old Royal Naval College Trinity Laban Chapel Choir: Handel Messiah"] == ["classical"]


def test_exhibitions_talks_courses_adult_comedy_and_off_site_dropped():
    titles = {e.title for e in _scraped()}
    joined = " | ".join(titles)
    for dropped in ("LIFEM26", "Exhibition", "Music Appreciation", "Sarah Raven", "Gospel Advanced",
                    "Gary Delaney", "Christmas Fair", "Flea Market", "Once Upon A Mattress"):
        assert dropped not in joined


def test_buildings():
    by_title = {e.title: e.venue_slug for e in _scraped()}
    assert by_title["Trinity Laban Symphony Orchestra"] == "blackheath-halls"
    assert by_title["Old Royal Naval College Trinity Laban Chapel Choir: Handel Messiah"] \
        == "old-royal-naval-college-chapel"
    assert set(by_title.values()) == {"blackheath-halls", "old-royal-naval-college-chapel"}
    # A blank Location falls back to the Halls' postcode.
    assert bh.venue({"attribute_EventPostcode": "Blackheath Halls SE3 9RQ"}, {}) == "blackheath-halls"
    assert bh.venue({"attribute_Location": "St Michael & All Angels Church, London, SE3 9JL"}, {}) is None
    assert bh.venue({"attribute_Location": "Laban Theatre"}, {}) == "laban-theatre"


def test_rules():
    assert bh.categorize({"attribute_Category": "Family, Dance"}) == ["kids", "dance"]
    assert bh.categorize({"attribute_Category": "jazz, music"}) == ["jazz"]
    assert bh.categorize({"attribute_Category": "Musical Theatre"}) == ["theater"]
    assert bh.categorize({"attribute_Category": "Exhibition, music"}) == []
    assert bh.categorize({"attribute_Category": "comedy"}) == []
    assert bh.categorize({}) == []


def test_free_price_from_the_price_attribute():
    events = _scraped()
    assert len({e.external_id for e in events}) == len(events)
    mozart = next(e for e in events if e.title == "Lunchtime Recital: MozART in London")
    assert mozart.price == "free"  # "Free " — the price list wasn't fetched offline
    waldstein = next(e for e in events if e.title == "Lunchtime Recital: Waldstein Trio")
    assert waldstein.price is None  # "£10" is not used: prices come from the price list
