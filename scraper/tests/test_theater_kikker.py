import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers import theater_kikker as tk

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 14)


def _agenda() -> str:
    return (FIXTURES / "theater_kikker_agenda.html").read_text()


def _events():
    details = json.loads((FIXTURES / "theater_kikker_details.json").read_text())
    return tk.parse_agenda(_agenda(), details, TODAY)


def test_whole_season_parses_with_unique_ids():
    events = _events()
    assert len(events) >= 150
    assert len({e.external_id for e in events}) == len(events)
    assert max(e.start_date for e in events) >= dt.date(2027, 4, 1)  # year inferred


def test_every_event_has_time_category_and_url():
    for e in _events():
        assert e.start_time is not None
        assert e.category_slugs and set(e.category_slugs) <= {"theater", "dance", "kids"}
        assert e.source_url.startswith(tk.BASE_URL + "/agenda/")


def test_price_coverage_and_full_price_of_a_discount_range():
    events = _events()
    assert sum(e.price is not None for e in events) / len(events) >= 0.9
    # Detail: "Van € 10,50 tot € 21,00" (U-pas half price … full price).
    assert any(e.price == "21€" for e in events)
    assert any(e.price == "sold-out" for e in events)


def test_youth_programme_is_kids():
    kids = [e for e in _events() if "kids" in e.category_slugs]
    assert len(kids) >= 20
    assert all("Jeugd" in e.annotations for e in kids)


def test_rentals_offsite_and_cancelled_rows_are_left_out():
    titles = {e.title for e in _events()}
    assert not any("HOLOBIONT" in t for t in titles)          # Boorstraat 107 (Theater Utrecht)
    assert not any("Stuntwoman" in t for t in titles)         # idem
    assert not any("Assets Liability" in t for t in titles)   # "Op locatie TK"
    assert tk.categorize(["Verhuur"]) is None
    assert tk.categorize(["Specials & festivals"]) is None
    assert tk.categorize(["Dans", "Language no problem"]) == ["dance"]


def test_language_no_problem_label():
    events = _events()
    lnp = [e for e in events if e.language]
    assert lnp and all(e.language == "Language no problem" for e in lnp)
    assert all("Language no problem" not in e.annotations for e in events)


def test_a_dates_rental_label_on_the_detail_page_drops_it():
    # TussenTijd is "Dans" on the card, but its detail rows say "Verhuur".
    assert not any(e.title == "TussenTijd" for e in _events())


def test_detail_row_labels_become_annotations():
    assert any("Try-out" in e.annotations for e in _events())
