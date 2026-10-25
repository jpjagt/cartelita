"""Almeida Theatre: the site's calendar + production pages (fixtures
captured 2026-10-25)."""

import datetime as dt
from pathlib import Path

from cartelera.scrapers import almeida_theatre as al

FIXTURES = Path(__file__).parent / "fixtures"


def _run():
    slots = al.parse_calendar((FIXTURES / "almeida_theatre_calendar.json").read_text())
    pages = {f"{al.SITE}/whats-on/{s}/": al.parse_production((FIXTURES / f"almeida_theatre_{s}.html").read_text())
             for s in ("desire-under-the-elms", "theatre-tour-2", "angel-to-olympus")}
    return slots, al.build(slots, pages, dt.date(2026, 10, 25))


def test_calendar_slots():
    slots, _events = _run()
    assert any("theatre-tour" in s.url for s in slots)
    assert all(s.start.year >= 2026 and s.title for s in slots)


def test_tour_dropped_productions_kept():
    _slots, events = _run()
    titles = {e.title for e in events}
    assert "Desire Under the Elms" in titles and "Theatre Tour" not in titles
    assert all(e.category_slugs == ["theater"] for e in events)
    assert len({e.external_id for e in events}) == len(events)
    assert any(e.price == "£10" for e in events if e.title == "Angel to Olympus")
