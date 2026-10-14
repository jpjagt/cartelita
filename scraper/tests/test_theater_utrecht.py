import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers import theater_utrecht as tu

FIXTURES = Path(__file__).parent / "fixtures"


def _items(lang: str) -> list[dict]:
    return json.loads((FIXTURES / f"theater_utrecht_programs_{lang}.json").read_text())


def _events():
    return tu.parse_programs(_items("nl"), _items("en"))


def test_only_performances_in_the_own_house():
    items = _items("nl")
    events = _events()
    assert len(items) > 100 and 15 <= len(events) < len(items) / 2
    kept_ids = {e.external_id for e in events}
    for it in items:
        if str(it["program"]["id"]) in kept_ids:
            assert tu.HOME_THEATER in tu._attrs(it["program"], "Theater")
    # Touring dates (Tilburg …) and Utrecht dates at SSBU / Kikker are out.
    titles_dates = {(e.title, e.start_date) for e in events}
    assert not any(t == "SEXODUS." for t, _ in titles_dates)


def test_fields():
    events = _events()
    assert len({e.external_id for e in events}) == len(events)
    for e in events:
        assert e.category_slugs == ["theater"]
        assert e.source_url.startswith(tu.BASE_URL + "/nl/agenda/")
        assert e.start_date >= dt.date(2026, 10, 14)
    assert sum(e.start_time is not None for e in events) == len(events)


def test_price_from_the_one_liner():
    events = _events()
    by_title = {e.title: e for e in events}
    # "Zaterdag 17 oktober | 15:30 | Studio 3 | €10 / €7,50" → highest.
    assert by_title["BISMILLAH -NL-"].price == "10€"
    assert by_title["OP DREEF (5+)"].price == "5€"
    assert any(e.price == "free" for e in events)
    # No price stated (tickets via Stager, never fetched) → None.
    assert any(e.price is None for e in events)


def test_english_translation_by_program_id():
    vv = next(e for e in _events() if e.title.startswith("Melyn Chow"))
    assert vv.translations and vv.translations[0].lang == "en"
    assert vv.translations[0].title == "VV"
    assert vv.translations[0].source_url.startswith(tu.BASE_URL + "/en/agenda/")
