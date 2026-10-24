"""Cadogan Hall on the shared Spektrix helper, against saved API responses
(captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import cadogan_hall as cad

FIXTURES = Path(__file__).parent / "fixtures"


def _scraped():
    events = json.loads((FIXTURES / "cadogan_hall_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "cadogan_hall_spektrix_instances.json").read_text())
    return spk.build(cad.CLIENT, spk.select(events, instances, cad.categorize), {}, url=cad.web_url)


def test_categories_from_genre_labels():
    by_title = {e.title: e.category_slugs for e in _scraped()}
    assert by_title["Ralph McTell"] == ["folk"]
    assert by_title["Frankenstein (1931)"] == ["film"]
    assert by_title["The Snowman In Concert"] == ["classical", "kids"]
    assert by_title["LJF: Gerald Clayton Trio"] == ["jazz"]
    assert by_title["A Concert For Remembrance Day"] == ["classical"]


def test_tributes_pop_talks_and_ancillaries_dropped():
    titles = {e.title for e in _scraped()}
    joined = " | ".join(titles)
    for dropped in ("Illegal Eagles", "This Flight Tonight", "Gareth Malone", "Kingdom Choir",
                    "Wonderful", "BBC Big Band", "Secure My Booking", "Prosecco", "OTL:",
                    "Electoral Dysfunction", "Go West"):
        assert dropped not in joined


def test_web_url_preferred_and_stripped():
    events = _scraped()
    assert len({e.external_id for e in events}) == len(events)
    assert all(e.source_url == e.source_url.strip() for e in events)
    mctell = next(e for e in events if e.title == "Ralph McTell")
    assert mctell.source_url == "https://cadoganhall.com/whats-on/ralph-mctell/"
    assert cad.web_url({"webUrl": "https://cadoganhall.com/whats-on/handels-messiah/ "}) == \
        "https://cadoganhall.com/whats-on/handels-messiah/"
    assert cad.web_url({"webUrl": ""}) is None
