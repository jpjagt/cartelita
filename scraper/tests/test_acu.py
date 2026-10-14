import datetime as dt
from pathlib import Path

from cartelera.scrapers.acu import categorize, format_price, parse_agenda

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 14)


def _events():
    return parse_agenda((FIXTURES / "acu_agenda.html").read_text(), TODAY)


def _by_title(fragment: str):
    return next(e for e in _events() if fragment in e.title)


def test_keeps_programme_only():
    events = _events()
    assert len(events) == 25
    titles = " | ".join(e.title for e in events)
    # Community/side activities by the venue's own labels.
    for left_out in ("Koffie verQueerd", "Queer D&D", "The Barricade", "Draadverbinders",
                     "Int’l Open Stage", "Flying Carpet", "Against Capitalism", "Drag me"):
        assert left_out not in titles
    # Placeholder entries dated 2040/2057.
    assert all(e.start_date < dt.date(2029, 1, 1) for e in events)


def test_fields_and_unique_occurrences():
    events = _events()
    for ev in events:
        assert ev.source_url.startswith("https://acu.nl/events/")
        assert ev.start_time is not None
        assert ev.price is not None
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))
    # The site double-lists one EECtronic night; it appears once.
    assert sum(1 for e in events if e.title == "EECtronic open stage" and e.start_date == dt.date(2026, 12, 15)) == 1


def test_categories_from_labels():
    assert _by_title("Nothing Works").category_slugs == ["alternative"]
    assert _by_title("Nekrotsoulithra").category_slugs == ["alternative", "club"]
    assert _by_title("Sorrow’s Sanctuary").category_slugs == ["club"]
    assert _by_title("Foul Film Festival").category_slugs == ["film"]
    assert categorize(["AgendaEntry"]) == ["alternative"]  # unlabelled
    assert categorize(["AgendaEntry", "food", "info-talks"]) is None
    assert categorize(["AgendaEntry", "bands", "jam-sessions"]) is None


def test_time_prefers_start_over_door():
    ev = _by_title("Nothing Works")
    assert ev.start_date == dt.date(2026, 10, 16) and ev.start_time == dt.time(20, 30)


def test_price_formats():
    assert format_price("€ 8/12") == "12€"
    assert format_price("€ 5/15") == "5–15€"
    assert format_price("€ 16") == "16€"
    assert format_price("It’s Free!") == "free"
    assert format_price("Donation based") == "donation"
    assert _by_title("Isoler").price == "25€"
