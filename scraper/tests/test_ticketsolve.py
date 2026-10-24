"""The shared Ticketsolve helper and its venues (Conway Hall, New Diorama,
Jermyn Street), against saved feeds (captured 2026-10-25)."""

import datetime as dt
from pathlib import Path

from cartelera.scrapers import _ticketsolve as ts
from cartelera.scrapers import conway_hall, jermyn_street_theatre, new_diorama_theatre

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 25)


def _shows(name):
    return ts.parse_shows((FIXTURES / f"{name}_ticketsolve_shows.xml").read_bytes())


def _events(name, module):
    selected = ts.select(_shows(name), module.keep, TODAY)
    return ts.build(selected, {})


def test_parse_shows_and_performances():
    shows = _shows("conway_hall")
    assert len(shows) == 22
    concert = next(s for s in shows if s.name == "Sunday Concerts: Aida Piano Trio")
    assert concert.venue == "Conway Hall"
    assert concert.category == "Sunday Concerts"
    assert "sundayconcerts" in concert.tags
    perf = concert.events[0]
    assert perf.start == dt.datetime(2026, 11, 1, 18, 30)
    assert perf.url == "https://conwayhall.ticketsolve.com/shows/1173675508/events/428788203"
    assert perf.feed_url.endswith("/events/428788203.xml")
    assert concert.description and "<" not in concert.description


def test_conway_hall_keeps_only_the_sunday_concerts():
    events = _events("conway_hall", conway_hall)
    assert len(events) == 8
    assert all(e.title.startswith("Sunday Concerts:") for e in events)
    assert all(e.category_slugs == ["classical"] for e in events)
    assert all(e.start_time == dt.time(18, 30) for e in events)
    titles = {s.name for s in _shows("conway_hall")} - {e.title for e in events}
    assert "Lunchtime Recitals: Edward Lloyd" in titles  # uncategorised: dropped
    assert "Winter Carols by Candlelight" in titles  # "Music" hire: dropped


def test_online_streams_never_count():
    # Talks have an In Person and an Online performance at the same time.
    talk = next(s for s in _shows("conway_hall") if s.name == "Why Pubs Matter")
    kept = ts.select([talk], lambda show, perf: ["classical"], TODAY)
    assert [p.layout for _s, p, _c in kept] == ["Brockway Room Seated"]


def test_theatres_keep_every_performance_as_theater():
    for name, module in (("new_diorama_theatre", new_diorama_theatre),
                         ("jermyn_street_theatre", jermyn_street_theatre)):
        shows = _shows(name)
        upcoming = sum(1 for s in shows for p in s.events if p.start.date() >= TODAY)
        events = _events(name, module)
        assert len(events) == upcoming > 0
        assert all(e.category_slugs == ["theater"] for e in events)
        assert len({e.external_id for e in events}) == len(events)


def test_sold_out_and_annotations():
    events = _events("jermyn_street_theatre", jermyn_street_theatre)
    assert any(e.price == "sold-out" for e in events)
    assert any(e.annotations == ["relaxed show"] for e in events)
    nd = _events("new_diorama_theatre", new_diorama_theatre)
    assert {"preview", "pay what you can", "captioned", "relaxed"} <= {a for e in nd for a in e.annotations}


def test_prices_from_event_feeds():
    # Conway: Supporter £20 / Standard £14 / concessions… → the Standard ticket
    assert ts.price_text((FIXTURES / "conway_hall_ticketsolve_event.xml").read_bytes()) == "£14"
    # Jermyn Street: Full Price £40 / Concession £35
    assert ts.price_text((FIXTURES / "jermyn_street_theatre_ticketsolve_event.xml").read_bytes()) == "£40"
    # New Diorama pay-what-you-can ladder £5…£25
    assert ts.price_text((FIXTURES / "new_diorama_theatre_ticketsolve_event_pwyc.xml").read_bytes()) == "£5–25"
    assert ts.price_text("<event><prices></prices></event>") is None
    free = "<event><prices><price><type>Free</type><face_price>0.0</face_price></price></prices></event>"
    assert ts.price_text(free) == "free"
