"""Offline tests for the PizzaExpress Live source (saved API pages)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers import load_all
from cartelera.scrapers.pizzaexpress_live import (
    SOURCE_SLUG,
    events_from_items,
    parse_date,
    parse_time,
)

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 24)


def _items() -> list[dict]:
    items = []
    for p in (1, 11):
        items.extend(json.loads((FIXTURES / f"pizzaexpress_live_page{p}.json").read_text())["hydra:member"])
    return items


def test_date_and_time():
    assert parse_date("Saturday 24th October", TODAY) == dt.date(2026, 10, 24)
    # Year from the weekday: 28 April 2027 is a Wednesday.
    assert parse_date("Wednesday 28th April", TODAY) == dt.date(2027, 4, 28)
    assert parse_date("Friday 1st January", dt.date(2026, 12, 20)) == dt.date(2027, 1, 1)
    assert parse_time("8:00PM") == dt.time(20)
    assert parse_time("12:00PM") == dt.time(12)
    assert parse_time("1:00PM") == dt.time(13)


def test_only_soho_kept_by_location_field():
    items = _items()
    locations = {i["location"] for i in items}
    assert {"Soho", "Holborn", "Chelsea"} <= locations
    events = events_from_items(items, TODAY)
    soho = [i for i in items if i["location"] == "Soho"]
    assert len(events) == len(soho)
    assert {e.venue_slug for e in events} == {"pizzaexpress-jazz-club-soho"}
    assert all(e.category_slugs == ["jazz"] for e in events)
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))


def test_event_fields():
    events = events_from_items(_items(), TODAY)
    joanna = next(e for e in events if e.title == "Joanna Eden Band")
    assert joanna.start_date == dt.date(2026, 10, 25)
    assert joanna.start_time == dt.time(20)
    assert joanna.price == "£25"
    assert joanna.source_url == "https://www.pizzaexpresslive.com/whats-on/joanna-eden-band"
    assert joanna.image_url.startswith("https://assets.pizzaexpresslive.com/")
    assert joanna.annotations == ["Doors 6:30PM"]
    # No seats left -> sold out.
    buena = next(e for e in events if e.title == "Buena Vista Social Club Live Revue")
    assert buena.price == "sold-out"
    assert all(e.price for e in events)


def test_past_dropped():
    events = events_from_items(_items(), dt.date(2026, 10, 25))
    assert all(e.start_date >= dt.date(2026, 10, 25) for e in events)
    assert not any(e.title == "Buena Vista Social Club Live Revue" for e in events)


def test_registered():
    _scraper, source = load_all()[SOURCE_SLUG]
    assert [v.slug for v in source.venues] == ["pizzaexpress-jazz-club-soho"]
    assert source.venues[0].city_slug == "london"
