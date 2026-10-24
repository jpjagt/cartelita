"""St James's Piccadilly from its WordPress events REST, against saved
posts of the kept categories (captured 2026-10-25)."""

import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers import _yearless
from cartelera.scrapers import st_james_piccadilly as sjp

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 25)


def _events(today=TODAY):
    data = json.loads((FIXTURES / "st_james_piccadilly_events.json").read_text())
    return sjp.parse(data["posts"], data["past_events_id"], today)


def test_free_lunchtime_recitals_and_the_sixteen():
    events = _events()
    assert len(events) == 12
    assert all(e.category_slugs == ["classical"] for e in events)
    assert len({e.external_id for e in events}) == len(events)
    lunchtime = [e for e in events if e.start_time == dt.time(13, 10)]
    assert len(lunchtime) >= 8 and all(e.price == "free" for e in lunchtime)


def test_date_time_and_year_from_the_hero():
    by_title = {e.title: e for e in _events()}
    wu = by_title["Nicole Wu (piano)"]  # "Wednesday 25 November 1.10pm"
    assert (wu.start_date, wu.start_time) == (dt.date(2026, 11, 25), dt.time(13, 10))
    sixteen = by_title["Music for All Saints and All Souls"]  # "Tuesday 27 October 7pm"
    assert (sixteen.start_date, sixteen.start_time) == (dt.date(2026, 10, 27), dt.time(19, 0))
    assert sixteen.price is None  # sold on thesixteen.com
    assert sixteen.source_url == "https://www.sjp.org.uk/whats-on/music-for-all-saints-and-all-souls/"
    assert by_title["Christmas Choral Tots"].price == "£5–10"  # Adult £10/Child £5


def test_passed_and_past_events_dropped():
    assert all(e.start_date >= dt.date(2026, 11, 1) for e in _events(dt.date(2026, 11, 1)))
    data = json.loads((FIXTURES / "st_james_piccadilly_events.json").read_text())
    post = data["posts"][0]
    post["event-category"] = [*post["event-category"], data["past_events_id"]]
    assert len(sjp.parse(data["posts"], data["past_events_id"], TODAY)) == 11


def test_yearless_dates():
    anchor = dt.date(2026, 10, 15)
    assert _yearless.parse("Wednesday 25 November 1.10pm", anchor) == dt.date(2026, 11, 25)
    assert _yearless.parse("Mon 4th January", anchor) == dt.date(2027, 1, 4)
    assert _yearless.parse("Fri 20th August", anchor) == dt.date(2027, 8, 20)
    assert _yearless.parse("3 December", anchor) == dt.date(2026, 12, 3)
    assert _yearless.parse("Doors at 7pm", anchor) is None
    assert _yearless.parse_time("Thursday 3 December 6.15pm") == dt.time(18, 15)
    assert _yearless.parse_time("Tue 27th October 7:00pm") == dt.time(19, 0)
    assert _yearless.parse_time("Saturday 28 November 10am") == dt.time(10, 0)
