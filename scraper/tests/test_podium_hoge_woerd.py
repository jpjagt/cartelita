import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers import podium_hoge_woerd as hw

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 14)


def _pages() -> list[str]:
    return [(FIXTURES / f"podium_hoge_woerd_agenda_{i}.html").read_text() for i in (1, 2, 3)]


def _events():
    details = json.loads((FIXTURES / "podium_hoge_woerd_details.json").read_text())
    return hw.parse_agenda(_pages(), details, TODAY)


def test_overlapping_date_pages_dedupe_per_occurrence():
    events = _events()
    assert len(events) >= 20
    assert len({e.external_id for e in events}) == len(events)
    # Pages restart at the previous page's last date, so they overlap.
    assert hw.last_date(_pages()[0], TODAY) <= hw.last_date(_pages()[1], TODAY)


def test_fields_and_coverage():
    events = _events()
    for e in events:
        assert e.title and e.start_time is not None and e.start_date >= TODAY
        assert e.category_slugs and set(e.category_slugs) <= {"theater", "dance", "kids", "pop"}
    assert sum(e.price is not None for e in events) / len(events) >= 0.9


def test_card_spans_title_vs_company():
    ev = next(e for e in _events() if e.title == "Wat niemand zag")
    assert ev.description == "Betty Loha"
    assert ev.category_slugs == ["theater"]


def test_categorize_rules():
    assert hw.categorize(["Cabaret"]) == ["theater"]
    assert hw.categorize(["Jeugd"]) == ["kids"]
    assert hw.categorize(["Muziek"]) == ["pop"]
    assert hw.categorize(["Muziek", "Verhuur"]) is None
    assert hw.categorize(["Talks"]) is None
    assert hw.categorize(["Workshop", "Circustheater"]) is None
    assert hw.categorize(["Dans", "No Dutch? No Problem!"]) == ["dance"]
