import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers.maas import (
    BASE_URL,
    categorize,
    detail_urls,
    parse_detail,
    parse_shows,
)

FIXTURES = Path(__file__).parent / "fixtures"
DATA = json.loads((FIXTURES / "maas_showsearch.json").read_text())
PREFIX = "maas_show_"


def _details() -> dict[str, str]:
    return {
        f"{BASE_URL}/nl/agenda/{p.stem[len(PREFIX):]}/": p.read_text()
        for p in FIXTURES.glob(f"{PREFIX}*.html")
    }


def _events():
    return parse_shows(DATA, _details())


def _by_url(fragment: str):
    return [e for e in _events() if f"/agenda/{fragment}/" in e.source_url]


def test_detail_fixtures_are_production_pages_the_scraper_fetches():
    assert set(_details()) <= set(detail_urls(DATA))


def test_only_maaspodium_performances_are_kept():
    events = _events()
    maaspodium = [s for s in DATA["Shows"] if s["ShowZaal"]["IsMaaspodium"]]
    touring = [s for s in DATA["Shows"] if not s["ShowZaal"]["IsMaaspodium"]]
    assert touring and len(events) <= len(maaspodium)
    assert len(events) > 80
    assert {e.venue_slug for e in events} == {"maaspodium"}
    touring_ids = {str(s["EventId"]) for s in touring}
    assert not touring_ids & {e.external_id for e in events}


def test_events_have_dates_titles_urls_categories():
    for ev in _events():
        assert dt.date(2026, 10, 1) <= ev.start_date <= dt.date(2027, 12, 31)
        assert ev.title
        assert ev.source_url.startswith(f"{BASE_URL}/nl/agenda/")
        assert ev.category_slugs
        assert set(ev.category_slugs) <= {"theater", "dance", "kids"}
        assert ev.start_time is not None


def test_external_ids_unique():
    ids = [e.external_id for e in _events()]
    assert len(ids) == len(set(ids))


def test_parse_detail_genre_and_price():
    d = parse_detail((FIXTURES / "maas_show_fabrica.html").read_text())
    assert d == {"genres": ["Fysiek theater", "Danstheater", "Dans"], "price": "12,50€"}
    d = parse_detail((FIXTURES / "maas_show_samar-en-de-bange-koning.html").read_text())
    assert d["price"] == "10€"
    assert parse_detail(
        (FIXTURES / "maas_show_open-atelier-onder-de-dertien-volle-manen.html").read_text()
    ) is None


def test_category_from_genre_and_age():
    assert categorize(["Fysiek theater", "Danstheater", "Dans"], "Jongeren en volwassenen") == [
        "theater", "dance",
    ]
    assert categorize(["Danstheater"], "4+") == ["dance", "kids"]
    assert categorize(["Muziektheater"], "8+") == ["theater", "kids"]
    assert categorize(["Theater"], "14+") == ["theater"]
    assert categorize(["Dans", "Workshop"], None) is None
    assert categorize([], "8+") == ["theater", "kids"]


def test_fabrica_is_dance_and_theater_with_price():
    (ev,) = _by_url("fabrica")
    assert ev.category_slugs == ["theater", "dance"]
    assert ev.price == "12,50€"
    assert ev.start_time == dt.time(19, 30)


def test_workshop_and_open_atelier_are_excluded():
    assert _by_url("ballroom-thursdays") == []
    assert _by_url("open-atelier-onder-de-dertien-volle-manen") == []


def test_midnight_placeholders_dropped_next_to_timed_sessions():
    zmd = [e for e in _by_url("zeg-maar-dag") if e.start_date == dt.date(2027, 3, 28)]
    assert sorted(e.start_time for e in zmd) == [dt.time(13, 0), dt.time(16, 0)]


def test_sold_out_flag():
    sold = [e for e in _events() if e.price == "sold-out"]
    assert sold
