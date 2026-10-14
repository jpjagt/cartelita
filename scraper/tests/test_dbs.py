import json
from pathlib import Path

from cartelera.scrapers.dbs import categorize, is_programme, parse_events

FIXTURES = Path(__file__).parent / "fixtures"


def _raw():
    return [
        e
        for page in ("dbs_events_p1.json", "dbs_events_p2.json")
        for e in json.loads((FIXTURES / page).read_text())["events"]
    ]


def _events():
    return parse_events(_raw())


def test_parses_every_programme_event_from_both_pages():
    raw = _raw()
    assert len(raw) == 62
    events = _events()
    # 4 bar nights (tap takeover, karaoke, metal quiz, pop pub quiz) left out.
    assert len(events) == 58


def test_fields_are_populated():
    for ev in _events():
        assert ev.title and "&#" not in ev.title
        assert ev.source_url.startswith("https://dbstudio.nl/event/")
        assert ev.start_time is not None
        assert ev.external_id and ev.external_id.isdigit()
        assert set(ev.category_slugs) <= {"pop", "alternative"} and ev.category_slugs
    ids = [e.external_id for e in _events()]
    assert len(ids) == len(set(ids))
    assert sum(1 for e in _events() if e.image_url) >= 50


def test_bar_nights_are_not_programme():
    titles = {e.title for e in _events()}
    assert not any("Tap Takeover" in t or "Karaoke" in t or "Quiz" in t or "METALQUIZ" in t for t in titles)
    assert not is_programme(["Bier specials", "Cafe", "Tap Takeover"])
    assert not is_programme(["Cafe"])
    # A café concert is a concert.
    assert is_programme(["Afrika", "Cafe", "Concert"])


def test_pop_vs_alternative_from_venue_labels():
    assert categorize(["Dream Pop"]) == ["pop"]
    assert categorize(["Concert", "Pop", "Postrock"]) == ["pop", "alternative"]
    assert categorize(["Black Metal", "Metal"]) == ["alternative"]
    assert categorize([]) == ["alternative"]
    ruby = next(e for e in _events() if "RUBY HAUNT" in e.title)
    assert ruby.category_slugs == ["pop"]
    kanaan = next(e for e in _events() if "KANAAN" in e.title)
    assert kanaan.category_slugs == ["alternative"]
    assert "Krautrock" in kanaan.annotations and "Concert" not in kanaan.annotations


def test_no_price_on_the_site():
    # dB's sells via Stager only; the Tribe cost field is empty for shows.
    assert all(e.price is None for e in _events())
