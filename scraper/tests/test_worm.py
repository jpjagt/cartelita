import datetime as dt
from pathlib import Path

from cartelera.scrapers.worm import (
    build_events,
    category_for,
    detail_urls,
    parse_agenda,
    parse_detail,
)

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA = FIXTURES / "worm_agenda.html"
PREFIX = "worm_detail_"


def _details() -> dict[str, str]:
    return {
        f"https://worm.org/production/{p.stem[len(PREFIX):]}/": p.read_text()
        for p in FIXTURES.glob(f"{PREFIX}*.html")
    }


def _events():
    return build_events(AGENDA.read_text(), _details())


def _by_title(fragment: str):
    return next(e for e in _events() if fragment.lower() in e.title.lower())


def test_agenda_items_with_dates_from_month_headers():
    items = parse_agenda(AGENDA.read_text())
    assert len(items) >= 30
    assert all(i["url"].startswith("https://worm.org/production/") for i in items)
    # "Sun 24 January" sits under the "January 2027" header.
    jan = next(i for i in items if "Mark Lotterman" in i["title"])
    assert jan["date"] == dt.date(2027, 1, 24)


def test_category_is_worms_own_label():
    assert category_for("FIlm") == "film"
    assert category_for("Club") == "club"
    assert category_for("Concert") == "alternative"
    assert category_for("Theatre / Performance") == "alternative"
    for excluded in ("Community", "Workshop", "Talk", "Broadcast / Stream", "Art & expo"):
        assert category_for(excluded) is None
    assert _by_title("GENDER TROUBLE").category_slugs == ["film"]
    assert _by_title("perreo31").category_slugs == ["club"]
    assert _by_title("Reona/Savic").category_slugs == ["alternative"]


def test_non_programme_items_are_dropped():
    titles = " | ".join(e.title for e in _events())
    assert "Singing Club" not in titles
    assert "Art-Gang" not in titles
    assert "Rotterdam Late Night" not in titles
    assert all(u in {e.source_url for e in _events()} for u in detail_urls(AGENDA.read_text()))


def test_time_from_production_page():
    assert parse_detail((FIXTURES / "worm_detail_gender-trouble.html").read_text()) == (
        dt.date(2026, 10, 14), dt.time(20, 30))
    assert _by_title("perreo31").start_time == dt.time(23, 0)
    assert _by_title("Reona/Savic").start_date == dt.date(2026, 10, 24)
    # Without a fetched detail page the time stays unknown.
    assert _by_title("SILVER SILLON").start_time is None


def test_events_valid_and_unique():
    events = _events()
    assert len(events) >= 15
    for e in events:
        assert e.title and e.start_date >= dt.date(2026, 10, 14)
        assert e.price is None
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))
