"""Smith Square Hall (Sinfonia Smith Square) on the shared Spektrix helper,
against saved API responses (captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import sinfonia_smith_square as sss

FIXTURES = Path(__file__).parent / "fixtures"


def _scraped():
    events = json.loads((FIXTURES / "sinfonia_smith_square_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "sinfonia_smith_square_spektrix_instances.json").read_text())
    return spk.build(sss.CLIENT, spk.select(events, instances, sss.categorize), {})


def test_categories_from_type_and_series():
    by_title = {e.title: e.category_slugs for e in _scraped()}
    assert by_title["LFBM 2026: Bach Orchestral Suites"] == ["classical"]
    assert by_title["5pence and the Kodie Kollective"] == ["jazz"]  # Jazz in the Crypt
    assert by_title["NYJO Blueprint Orchestra"] == ["jazz"]  # Type Jazz
    assert by_title["The Snowman Live in Concert"] == ["classical", "kids"]
    # No Type, but a house series (Christmas Festival).
    assert by_title["Winterreise with Roderick Williams"] == ["classical"]


def test_drops_other_venues_upsells_and_unlabelled():
    titles = {e.title for e in _scraped()}
    joined = " | ".join(titles)
    assert "Westminster Abbey" not in joined
    assert "post-show reception" not in joined
    assert "Siglo de Oro: Hey for Christmas" not in titles  # neither Type nor Series


def test_one_row_per_performance_and_spektrix_urls():
    events = _scraped()
    assert len({e.external_id for e in events}) == len(events)
    assert all(e.source_url.startswith(
        "https://checkout.sinfoniasmithsq.org.uk/sinfoniasmithsquare/website/EventDetails.aspx?EventId=")
        for e in events)
