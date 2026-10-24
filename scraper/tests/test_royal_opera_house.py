"""Royal Ballet and Opera (Royal Opera House) from the rbo.org.uk listing's
embedded state, against a trimmed saved listing and production page
(captured 2026-10-25)."""

import datetime as dt
from pathlib import Path

from cartelera.scrapers import royal_opera_house as roh

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 25)


def _listing():
    return (FIXTURES / "royal_opera_house_listing.html").read_text()


def _carmen_prices():
    return roh.production_prices((FIXTURES / "royal_opera_house_production_carmen.html").read_text())


def _events():
    page = "/production/carmen-damiano-michieletto"
    return roh.parse(_listing(), {page: _carmen_prices()}, today=TODAY)


def test_opera_is_classical_ballet_is_dance():
    by_title = {}
    for e in _events():
        by_title.setdefault(e.title, set()).update(e.category_slugs)
    assert by_title["Carmen"] == {"classical"}
    assert by_title["Swan Lake"] == {"dance"}
    assert by_title["4.48 Psychosis"] == {"classical"}  # Linbury Theatre
    assert by_title["Female Power"] == {"dance"}  # Linbury Theatre
    assert all(len(cats) == 1 for cats in by_title.values())


def test_tours_talks_rehearsals_workshops_and_other_rooms_dropped():
    titles = {e.title for e in _events()}
    for dropped in ("Behind the Scenes Tour", "Friends Rehearsals", "Family Sundays",
                    "Insights: Götterdämmerung", "Recitals at Lunch",  # Crush Room
                    "Live at Lunch", "Tea Dance",  # building-wide, not a stage
                    "Dish from Waitrose",  # no genre tag
                    "Romeo and Juliet"):  # cinema season card
        assert dropped not in titles, dropped
    assert not any(t.startswith("<h4>") for t in titles)  # prismic-only cards


def test_only_public_performances_one_row_each():
    events = _events()
    carmen = [e for e in events if e.title == "Carmen"]
    # 10 listed: the schools matinee (13 Nov) is dropped, the relaxed one kept
    assert len(carmen) == 9
    assert dt.date(2026, 11, 13) not in {e.start_date for e in carmen}
    relaxed = next(e for e in carmen if e.start_date == dt.date(2026, 11, 8))
    assert relaxed.annotations == ["relaxed performance"]
    assert len({e.external_id for e in events}) == len(events)
    assert all(e.start_date >= TODAY for e in events)


def test_carmen_fields_and_prices():
    carmen = {e.start_date: e for e in _events() if e.title == "Carmen"}
    first = carmen[dt.date(2026, 10, 29)]
    assert first.start_time == dt.time(19, 0)
    assert first.price == "£23–343"
    assert carmen[dt.date(2026, 11, 10)].price == "£47–273"
    assert first.source_url == "https://www.rbo.org.uk/production/carmen-damiano-michieletto"
    assert first.external_id == "54683@2026-10-29T19:00"
    assert all(e.price for e in carmen.values())


def test_production_prices_sold_out_and_unknown():
    page = """<script>window.__REACT_QUERY_DEHYDRATED_STATE__ = {"queries": [
      {"state": {"data": {"data": {"stage": {"activities": [
        {"id": "1", "type": "stage-activity", "attributes": {"date": "2026-12-01T19:30:00+00:00"}},
        {"id": "2", "type": "stage-activity", "attributes": {"date": "2026-12-02T19:30:00+00:00"}}]}}}}},
      {"state": {"data": {"included": [
        {"id": "1", "type": "activityAvailability", "attributes": {"ticketsAvailable": 0,
         "minPriceAvailable": null, "maxPriceAvailable": null}},
        {"id": "2", "type": "activityAvailability", "attributes": {"ticketsAvailable": 4,
         "minPriceAvailable": null, "maxPriceAvailable": null}}]}}}]};</script>"""
    prices = roh.production_prices(page)
    assert prices == {dt.datetime(2026, 12, 1, 19, 30): "sold-out"}
