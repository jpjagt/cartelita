import datetime as dt
from pathlib import Path

from cartelera.scrapers.roodkapje import build_events, parse_agenda

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA = FIXTURES / "roodkapje_agenda.html"
PREFIX = "roodkapje_detail_"


def _details():
    return {
        f"https://roodkapje.org/event/{p.stem[len(PREFIX):]}/": p.read_text()
        for p in FIXTURES.glob(f"{PREFIX}*.html")
    }


def _events():
    return build_events(AGENDA.read_text(), _details())


def _by_title(fragment: str):
    return next(e for e in _events() if fragment.lower() in e.title.lower())


def test_agenda_items_carry_roodkapje_category():
    items = parse_agenda(AGENDA.read_text())
    assert len(items) >= 3
    assert all("live" in i["categories"] for i in items)
    assert all(i["url"].startswith("https://roodkapje.org/event/") for i in items)


def test_live_events_are_alternative_with_time_and_price():
    events = _events()
    assert len(events) >= 3
    assert all(e.category_slugs == ["alternative"] for e in events)
    vmg = _by_title("Velocity Made Good")
    assert vmg.start_date == dt.date(2026, 10, 30)
    assert vmg.start_time == dt.time(20, 30)          # "Start: 20:30"
    alden = _by_title("Alexandra Alden")
    assert alden.start_time == dt.time(20, 30)        # ticket line "20:30-23:00"
    assert alden.price == "sold-out"
    assert _by_title("Yuraa").price == "15€"          # "tickets 15,-"


def test_art_only_items_are_left_out():
    html = AGENDA.read_text().replace("rk_event_category_live", "rk_event_category_art")
    assert build_events(html, _details()) == []


def test_ids_unique():
    ids = [e.external_id for e in _events()]
    assert len(ids) == len(set(ids))
