import datetime as dt
from pathlib import Path

import pytest

from cartelera.scrapers import lantarenvenster as L

FIX = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 14)  # fixture capture date


@pytest.fixture(scope="module")
def items():
    return L.parse_agenda((FIX / "lantarenvenster_home.html").read_text(), today=TODAY)


@pytest.fixture(scope="module")
def events(items):
    house = L.house_film_price((FIX / "lantarenvenster_kaartverkoop.html").read_text())
    details = {
        "https://www.lantarenvenster.nl/programma/the-cycle-of-love/":
            L.parse_detail((FIX / "lantarenvenster_film_detail.html").read_text()),
        "https://www.lantarenvenster.nl/programma/bill-stewart-trio-26/":
            L.parse_detail((FIX / "lantarenvenster_music_detail.html").read_text()),
    }
    return L.build_events(items, details, house)


def test_house_price():
    assert L.house_film_price((FIX / "lantarenvenster_kaartverkoop.html").read_text()) == "13€"


def test_one_event_per_production_per_day(events):
    assert len(events) > 200
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))
    for e in events:
        assert e.start_date >= TODAY
        assert e.source_url.startswith("https://www.lantarenvenster.nl/programma/")
        assert e.start_times and e.start_time == e.start_times[0]
    # "Yellow Letters" plays 13:40 and 18:45 on Oct 14 -> one row, two times.
    yl = next(e for e in events if e.title == "Yellow Letters" and e.start_date == TODAY)
    assert yl.start_times == [dt.time(13, 40), dt.time(18, 45)]


def test_categories(events):
    by = {e.title: e for e in events}
    assert by["Yellow Letters"].category_slugs == ["film"]
    assert next(e for e in events if e.title.startswith("Bill Stewart Trio")).category_slugs == ["jazz"]
    assert by["The Zawose Queens"].category_slugs == ["folk"]
    assert next(e for e in events if e.title.startswith("Moppervis")).category_slugs == ["kids"]
    cats = {c for e in events for c in e.category_slugs}
    assert cats == {"film", "jazz", "kids", "folk"}


def test_announced_without_screenings_are_skipped(events):
    # "Coward": "Verwacht vanaf do 22 okt" (no times yet) -> not an event
    assert not [e for e in events if e.title == "Coward"]


def test_exclusions(events):
    titles = {e.title for e in events}
    assert not [t for t in titles if t.startswith("Salsa aan de haven")]  # dans
    assert not [t for t in titles if t.startswith("Boekpresentatie")]
    assert not [t for t in titles if t.startswith(("Jazz Yoga", "Dial Q", "Rotterdams Open Doek"))]


def test_prices_and_language(events):
    bill = next(e for e in events if e.title.startswith("Bill Stewart Trio — met"))
    assert bill.price == "21€"
    cycle = next(e for e in events if e.title == "The Cycle of Love")
    assert cycle.price == "13€"  # "vanaf € 10" = the student tier -> house price
    assert cycle.language is not None
    films = [e for e in events if "film" in e.category_slugs]
    assert all(e.price for e in films)  # house price fallback


def test_detail_price():
    assert L.detail_price("€ 21 incl. € 3,00 servicekosten per ticket", film=False, house="13€") == "21€"
    assert L.detail_price("vanaf € 10", film=True, house="13€") == "13€"
    assert L.detail_price("vanaf € 10", film=False, house="13€") is None
    assert L.detail_price("gratis", film=False, house=None) == "free"
    assert L.detail_price("€ 17,50", film=False, house=None) == "17,50€"


def test_language_format():
    assert L._language("Dari, Pashtu gesproken", "Nederlands ondertiteld") == "Dari, Pashtu (Nederlands ondertiteld)"
    assert L._language("", "") is None
