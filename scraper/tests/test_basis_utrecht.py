import json
from pathlib import Path

from cartelera.scrapers.basis_utrecht import description_price, is_programme, parse_events

FIXTURES = Path(__file__).parent / "fixtures"


def _events():
    return parse_events(json.loads((FIXTURES / "basis_events.json").read_text())["events"])


def test_parses_club_nights():
    events = _events()
    # 21 listed; the free production class (labelled only "Other") is left out.
    assert len(events) == 20
    assert not any("Production Class" in e.title for e in events)
    for ev in events:
        assert ev.category_slugs == ["club"]
        assert ev.source_url.startswith("https://clubbasis.nl/event/")
        assert ev.start_time is not None
        assert "Other" not in ev.annotations
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))


def test_other_only_is_not_programme():
    assert not is_programme(["Other"])
    assert is_programme(["Experimental", "Other"])
    assert is_programme([])


def test_door_price_from_description_tiers():
    events = _events()
    priced = [e for e in events if e.price]
    assert len(priced) >= 17
    rebekah = next(e for e in events if "Rebekah" in e.title)
    assert rebekah.price == "20€"
    # "23:30 €15" must not read as 30€.
    assert all(e.price in {"20€", "22€", "23€"} for e in priced)


def test_description_price_unit():
    html = "<p>TICKETS<br />/ Early entry before 23:30 €17<br />/ Doorsale entry after 23:30 €23</p>"
    assert description_price(html) == "23€"
    assert description_price("<p>Line-up TBA</p>") is None
    assert description_price(None) is None
