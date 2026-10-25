"""The Old Vic: TNEW joined to the /stage/ pages (fixtures captured
2026-10-25)."""

import json
from pathlib import Path

from cartelera.scrapers import _tnew as tnew
from cartelera.scrapers import old_vic as ov

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name):
    return (FIXTURES / name).read_text()


def test_tnew_joined_to_stage_page():
    assert f"{ov.SITE}/stage/martin-guerre/" in ov.listing_links(_read("old_vic_listing.html"))
    perfs = tnew.performances(json.loads(_read("old_vic_tnew.json"))["productions"])
    page = ov.parse_stage(_read("old_vic_martin-guerre.html"), f"{ov.SITE}/stage/martin-guerre/")
    events = ov.build(perfs, [page])
    assert {e.title for e in events} == {"Martin Guerre"}  # storytelling has no page joined
    assert {e.price for e in events} <= {"£14.50–76.50", "sold-out"}
    assert any("captioned" in e.annotations for e in events)
    assert all(e.category_slugs == ["theater"] for e in events)
