"""Hampstead Theatre: what's-on production cards + production-page prices
(fixtures captured 2026-10-25)."""

import datetime as dt
from pathlib import Path

from cartelera.scrapers import hampstead_theatre as hp

FIXTURES = Path(__file__).parent / "fixtures"


def _events():
    prods = hp.parse_listing((FIXTURES / "hampstead_theatre_listing.html").read_text())
    for p in prods:
        p.price = hp.parse_price((FIXTURES / f"hampstead_theatre_{p.slug}.html").read_text())
    return prods, hp.build(prods, dt.date(2026, 10, 25))


def test_cards_rooms_and_slots():
    prods, events = _events()
    assert {(p.title, p.room) for p in prods} == {("Jumpers", "Main Stage"), ("Dogstar", "Downstairs")}
    assert events and all(e.category_slugs == ["theater"] for e in events)
    assert len({e.external_id for e in events}) == len(events)
    assert any("preview" in e.annotations for e in events)


def test_full_price_ladders_not_concessions():
    _prods, events = _events()
    assert {e.price for e in events if e.title == "Jumpers"} <= {"£25–65", "sold-out"}
    assert {e.price for e in events if e.title == "Dogstar"} <= {"£10–35", "sold-out"}
