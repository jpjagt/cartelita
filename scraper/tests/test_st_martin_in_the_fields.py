"""St Martin-in-the-Fields on the shared Spektrix helper, against saved API
responses (captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import st_martin_in_the_fields as smitf

FIXTURES = Path(__file__).parent / "fixtures"


def _raw():
    return json.loads((FIXTURES / "st_martin_in_the_fields_spektrix_events.json").read_text())


def _scraped():
    instances = json.loads((FIXTURES / "st_martin_in_the_fields_spektrix_instances.json").read_text())
    return spk.build(smitf.CLIENT, spk.select(_raw(), instances, smitf.categorize), {})


def test_candlelight_series_and_non_concerts_dropped():
    kept = {e.source_url for e in _scraped()}
    for event in _raw():
        sub = event.get("attribute_SubCategories")
        if sub in ("Candlelight Concerts", "Crypt Live", "Come and Sing", "Silent Disco") or \
                event.get("attribute_Category") != "Music":
            assert smitf.CLIENT.booking_url(event) not in kept, event["name"]
    titles = {e.title for e in _scraped()}
    assert not any("Candlelight" in t and "Ex Cathedra" not in t and "Christmas Classics" not in t
                   and "St John Passion" not in t for t in titles)
    assert "Liza Sings Streisand" not in titles  # Masterworks, but Genre "Not Applicable"


def test_kept_series():
    by_title = {e.title: e.category_slugs for e in _scraped()}
    assert by_title["BBC Singers: Songs of Farewell"] == ["classical"]  # Masterworks
    assert by_title["Festive Family Carols"] == ["classical", "kids"]
    assert any(c == ["classical"] for t, c in by_title.items() if "Choral Discovery" in t)
    events = _scraped()
    assert len({e.external_id for e in events}) == len(events)
