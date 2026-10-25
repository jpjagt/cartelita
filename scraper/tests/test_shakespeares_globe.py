"""Shakespeare's Globe: TNEW joined to the PERFORMANCES section (fixtures
captured 2026-10-25)."""

import json
from pathlib import Path

from cartelera.scrapers import _tnew as tnew
from cartelera.scrapers import shakespeares_globe as gl

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name):
    return (FIXTURES / name).read_text()


def test_only_the_performances_section_is_listed():
    links = gl.listing_links(_read("shakespeares_globe_listing.html"))
    assert f"{gl.SITE}/whats-on/julius-caesar/" in links
    assert not any("tour" in u for u in links)


def test_tnew_joined_to_show_page_with_per_performance_price():
    perfs = tnew.performances(json.loads(_read("shakespeares_globe_tnew.json"))["productions"])
    page = gl.parse_show(_read("shakespeares_globe_julius-caesar.html"), f"{gl.SITE}/whats-on/julius-caesar/")
    events = gl.build(perfs, [page])
    assert {e.title for e in events} == {"Julius Caesar"}  # exhibition, tours, MakeBeth dropped
    assert all(e.annotations == ["Sam Wanamaker Playhouse"] for e in events)
    assert all(e.price for e in events)
    assert any(e.price == "£5–89" for e in events)
    assert len({e.external_id for e in events}) == len(events)
