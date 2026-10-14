import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers import stadsschouwburg_utrecht as ss

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 14)
CATEGORIES = {"theater", "dance", "kids", "classical", "pop"}


def _page() -> str:
    return (FIXTURES / "stadsschouwburg_utrecht_agenda.html").read_text()


def _events():
    details = json.loads((FIXTURES / "stadsschouwburg_utrecht_details.json").read_text())
    kids = ss.programme_urls([(FIXTURES / "stadsschouwburg_utrecht_kids.html").read_text()])
    return ss.parse_agenda([_page()], details, kids, set(), TODAY)


def test_list_page_has_thirty_rows_and_a_pager():
    assert len(ss.parse_rows(_page())) == 30
    assert ss.page_count(_page()) >= 15


def test_events_are_dated_categorized_and_unique():
    events = _events()
    assert len(events) >= 25
    assert len({e.external_id for e in events}) == len(events)
    for e in events:
        assert e.title and e.source_url.startswith(ss.BASE_URL + "/agenda/")
        assert e.start_date >= TODAY and e.start_time is not None
        assert e.category_slugs and set(e.category_slugs) <= CATEGORIES


def test_price_coverage_from_detail_pages():
    events = _events()
    assert sum(e.price is not None for e in events) / len(events) >= 0.9
    # "€ 25,00 / € 21,00 / € 15,00 / t/m 18 jaar € 12,00": seat ranks, < 2x → highest.
    controle = next(e for e in events if e.title.startswith("CONTROLE"))
    assert controle.price == "25€"
    assert controle.category_slugs == ["dance"]
    assert "reprise" in controle.annotations


def test_status_overrides_price():
    events = _events()
    assert any(e.price == "sold-out" for e in events)
    assert any(e.price == "free" for e in events)


def test_kids_come_from_the_age_filter_not_the_title():
    events = _events()
    kids = [e for e in events if "kids" in e.category_slugs]
    assert kids
    # A 12+ show is youth, not kids: the age filter doesn't list it.
    assert "kids" not in next(e for e in events if e.title.startswith("CONTROLE")).category_slugs


def test_non_programme_rows_are_left_out():
    rows = ss.parse_rows(_page())
    excluded = [r for r in rows if not ss.keep(r)]
    # The Foodprogramma/Verdieping-only kids workshop.
    assert excluded and all(set(r.genres) <= {"Foodprogramma", "Verdieping"} for r in excluded)
    titles = {e.title for e in _events()}
    assert not any(t.startswith("Workshop Gezonde Snoep") for t in titles)


def test_categorize_rules():
    assert ss.categorize(["Toneel"]) == ["theater"]
    assert ss.categorize(["Opera"]) == ["classical"]
    assert ss.categorize(["Muziek"]) == ["pop"]
    assert ss.categorize(["Muziek", "Dans"]) == ["dance"]
    assert ss.categorize(["Foodprogramma", "Cabaret"]) == ["theater"]
    assert ss.categorize(["Verdieping"]) is None
    assert ss.categorize(["Theatercollege", "Show"]) is None
    assert ss.categorize([]) is None


def test_other_venues_rooms_are_left_out():
    row = ss.parse_rows(_page())[0]
    row.location = "KABUL à GoGo"
    assert not ss.keep(row)
