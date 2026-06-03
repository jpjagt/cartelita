import datetime as dt
from pathlib import Path

from cartelera.scrapers.meam import (
    parse_agenda,
    parse_price,
    normalize_price,
)

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA = FIXTURES / "meam_agenda.html"


def _events():
    return parse_agenda(AGENDA.read_text())


def test_parses_many_events():
    events = _events()
    assert len(events) >= 15  # the diary listing holds the full upcoming programme


def test_events_have_dates_titles_urls_and_known_category():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("https://www.meam.es/")
        assert ev.category_slugs and ev.category_slugs[0] in {"classical", "jazz"}


def test_series_split_off_the_title():
    # The ` | <series>` suffix must not remain in the title.
    for ev in _events():
        assert "|" not in ev.title


def test_classical_and_music_split():
    events = _events()
    classical = [e for e in events if e.category_slugs == ["classical"]]
    jazz = [e for e in events if e.category_slugs == ["jazz"]]
    assert classical, "expected Saturday Classics concerts -> classical"
    assert jazz, "expected Friday Blues / Sunday Sounds -> jazz"
    # Saturday Classics are the classical ones; Friday Blues the music ones.
    for e in classical:
        assert any(a.lower() == "saturday classics" for a in e.annotations)
    blues = [e for e in jazz if any("blues" in a.lower() for a in e.annotations)]
    assert blues, "expected at least one Friday Blues event categorized as jazz"


def test_series_captured_as_annotation_not_in_category():
    for ev in _events():
        assert ev.annotations, "every concert should carry its series annotation"
        # The series labels must never leak into the category slugs.
        for a in ev.annotations:
            assert a.lower() not in {"classical", "jazz"}


def test_every_event_has_a_time():
    events = _events()
    with_time = [e for e in events if e.start_time is not None]
    assert len(with_time) == len(events)


def test_external_ids_unique_per_occurrence():
    events = _events()
    ids = [e.external_id for e in events]
    assert all(ids)
    assert len(set(ids)) == len(ids), "external_id must be unique per occurrence"


def test_image_urls_present():
    events = _events()
    with_img = [e for e in events if e.image_url]
    assert len(with_img) >= len(events) * 0.9


# --- price parsing (detail page) -------------------------------------------


def test_parse_price_from_classics_detail():
    price = parse_price((FIXTURES / "meam_diary_classics.html").read_text())
    assert price == "18€"


def test_parse_price_from_blues_detail():
    price = parse_price((FIXTURES / "meam_diary_blues.html").read_text())
    assert price == "18€"


def test_normalize_price_rules():
    assert normalize_price("Advance ticket sales: 18.00€ / entrance: 18.00€") == "18€"
    assert normalize_price("12.50€") == "12.5€"
    assert normalize_price("Free admission") == "free"
    assert normalize_price("Entrada gratuïta") == "free"
    assert normalize_price("Sold out") == "sold-out"
    assert normalize_price("10€ / 22€") == "22€"  # highest public amount
    assert normalize_price(None) is None
    assert normalize_price("no price here") is None
