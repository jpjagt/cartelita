"""Wigmore Hall from its own listings API, against saved responses per
filter group (captured 2026-10-25)."""

import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers import wigmore_hall as wh

FIXTURES = Path(__file__).parent / "fixtures"


def _listings():
    return json.loads((FIXTURES / "wigmore_hall_listings.json").read_text())


def _events():
    return wh.parse(_listings())


def test_parses_every_kept_performance_once():
    events = _events()
    assert len(events) > 250
    assert len({e.external_id for e in events}) == len(events)
    assert all(e.source_url.startswith("https://www.wigmore-hall.org.uk/whats-on/") for e in events)
    assert all(e.start_time is not None for e in events)
    assert sum(1 for e in events if e.price) / len(events) >= 0.95


def test_categories_follow_the_sites_own_filters():
    events = _events()
    by_title = {}
    for e in events:
        by_title.setdefault(e.title, set()).update(e.category_slugs)
    assert by_title["Brad Mehldau piano"] == {"classical", "jazz"}  # jazz + piano
    assert by_title["Emmet Cohen Quintet"] == {"jazz"}
    assert by_title["Chamber Tots"] == {"kids"}
    assert by_title["Orsino Ensemble"] == {"classical"}
    assert all(set(e.category_slugs) <= {"classical", "jazz", "kids"} for e in events)


def test_learning_strands_and_unfiled_items_dropped():
    titles = {e.title for e in _events()}
    # music-for-the-moment (also filed under a genre), schools, imagine-series
    assert "Music for the Moment" not in titles
    assert not any(t.startswith("Schools Concert") for t in titles)
    assert not any(t.startswith("Imagine Series") for t in titles)
    # in no filter at all: a members' rehearsal, a talk
    assert not any(t.startswith("Members' Open Rehearsal") for t in titles)


def test_fields_of_one_performance():
    orsino = next(e for e in _events() if e.title == "Orsino Ensemble")
    assert orsino.start_date == dt.date(2026, 10, 26)
    assert orsino.start_time == dt.time(13, 0)
    assert orsino.price == "£18"  # "£18 (concessions £16)"
    assert orsino.description == "Barber, Mark Simpson and Nielsen"
    assert orsino.source_url == "https://www.wigmore-hall.org.uk/whats-on/202610261300"
    assert orsino.external_id == "61318"


def test_price_text():
    assert wh.price("£45 £38 £34 £27 £18") == "£18–45"
    assert wh.price("£40 £32 £26 £22") == "£40"  # < 2x spread: the top price
    assert wh.price("Children £6, Adults £8<br/><sub>+£1 booking fee per transaction</sub>") == "£8"
    assert wh.price("Free") == "free"
    assert wh.price("Free (ticket required)") == "free"
    assert wh.price("") is None
