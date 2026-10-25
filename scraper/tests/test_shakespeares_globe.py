"""Shakespeare's Globe: the show pages of the PERFORMANCES section (fixtures
captured 2026-10-25)."""

import datetime as dt
from pathlib import Path

from cartelera.scrapers import shakespeares_globe as gl

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name):
    return (FIXTURES / name).read_text()


def test_only_the_performances_section_is_listed():
    links = gl.listing_links(_read("shakespeares_globe_listing.html"))
    assert f"{gl.SITE}/whats-on/julius-caesar/" in links
    assert not any("tour" in u for u in links)


TODAY = dt.date(2026, 10, 25)


def test_show_page_lists_every_performance_with_its_price():
    page = gl.parse_show(_read("shakespeares_globe_julius-caesar.html"), f"{gl.SITE}/whats-on/julius-caesar/", TODAY)
    events = gl.build([page], TODAY)
    assert {e.title for e in events} == {"Julius Caesar"}
    assert all(e.annotations == ["Sam Wanamaker Playhouse"] for e in events)
    assert all(e.price for e in events)
    assert any(e.price == "£5–89" for e in events)
    assert len({e.external_id for e in events}) == len(events) == len(page.performances)
    first = events[0]
    # "FRI 6 NOVEMBER" / "7.30 PM" / basket.shakespearesglobe.com/57710/57711
    assert (first.start_date, first.start_time, first.external_id) == (dt.date(2026, 11, 6), dt.time(19, 30), "57711")


def test_listing_date_takes_the_year_from_the_weekday():
    assert gl.listing_date("FRI 6 NOVEMBER", TODAY) == dt.date(2026, 11, 6)
    assert gl.listing_date("SUN 11 APRIL", TODAY) == dt.date(2027, 4, 11)
    assert gl.listing_date("SUN 25 OCTOBER", TODAY) == dt.date(2026, 10, 25)
    assert gl.listing_date("TUE 25 OCTOBER", TODAY) is None  # not a Tuesday last, this or next year
    assert gl.listing_date("Tickets", TODAY) is None


def test_slot_time():
    assert gl.slot_time("7.30 PM") == dt.time(19, 30)
    assert gl.slot_time("1.00 PM") == dt.time(13, 0)
    assert gl.slot_time("12 PM") == dt.time(12, 0)
    assert gl.slot_time("11.30 AM") == dt.time(11, 30)
