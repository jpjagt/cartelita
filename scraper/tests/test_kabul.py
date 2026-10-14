import datetime as dt
from pathlib import Path

from cartelera.scrapers.kabul import BASE_URL, build_events, categorize, detail_time, parse_agenda

FIXTURES = Path(__file__).parent / "fixtures"
PREFIX = "kabul_event_"


def _rows():
    return parse_agenda((FIXTURES / "kabul_home.html").read_text())


def _details():
    return {
        f"{BASE_URL}/events/{p.stem[len(PREFIX):]}": p.read_text()
        for p in FIXTURES.glob(f"{PREFIX}*.html")
    }


def _events():
    return build_events(_rows(), _details())


def _by_slug(slug: str):
    return next(e for e in _events() if e.external_id == slug)


def test_agenda_keeps_programme_at_the_venue():
    slugs = [r["slug"] for r in _rows()]
    # 15 listed: off-site Centraal Museum night, the line-dance workshop and
    # five music-bingo nights ("hits") are left out.
    assert len(slugs) == 8
    assert "20261015" not in slugs  # Centraal Museum
    assert "20261029" not in slugs  # Workshop
    assert "20261016" not in slugs  # music bingo
    assert len(slugs) == len(set(slugs))
    # Every kept row has its detail page in the fixture set.
    assert {r["url"] for r in _rows()} <= set(_details())


def test_fields():
    for ev in _events():
        assert ev.title and ev.source_url.startswith(f"{BASE_URL}/events/")
        assert ev.start_date >= dt.date(2026, 10, 14)
        assert ev.category_slugs
    assert sum(1 for e in _events() if e.start_time) >= 7


def test_times_from_rich_text():
    assert _by_slug("20261016-2").start_time == dt.time(22, 0)
    assert _by_slug("20261022").start_time == dt.time(20, 0)
    # "From 4PM on Saturday 7, November"
    assert _by_slug("20261107").start_time == dt.time(16, 0)
    assert detail_time("<div class='richtext-regular'>TBA</div>") is None


def test_categories_and_free_label():
    assert categorize(["Club Night"]) == ["club"]
    assert categorize(["Live music", "Performance"]) == ["alternative"]
    assert categorize(["Free entry", "electronic", "triphop"]) == ["club", "alternative"]
    assert categorize([]) == ["club"]
    popronde = _by_slug("20261022")
    assert popronde.price == "free"
    assert "Free entry" not in popronde.annotations
    assert _by_slug("20261030").price is None
