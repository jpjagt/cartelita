"""Brixton House on the Spektrix helper, against saved API responses and a
show page (captured 2026-10-24)."""

import json
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import brixton_house as bh

FIXTURES = Path(__file__).parent / "fixtures"
PROVIDERS_PAGE = "https://brixtonhouse.co.uk/shows/providers-2027/"


def _load():
    events = json.loads((FIXTURES / "brixton_house_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "brixton_house_spektrix_instances.json").read_text())
    return events, instances


def _programme(site=None):
    events, instances = _load()
    site = site or {}
    pages = spk.site_urls({u: ids for u, (ids, _p) in site.items()}, events, instances)
    return spk.build(bh.CLIENT, spk.select(events, instances, bh.categorize), {},
                     title=bh.title, url=lambda e: pages.get(e["id"]), finish=bh.site_price(site))


def test_artistic_season_new_writing_youth_and_family():
    cats = {e.title: e.category_slugs for e in _programme()}
    assert cats == {
        "Baby": ["theater"],
        "No Apologies!": ["theater"],
        "I AM: ONE OF MANY": ["theater"],
        "Providers": ["theater"],  # Youth Theatre in Season 10; "[2027]" stripped
        "Santa's Christmas Cold: An Orchestral Arctic Adventure": ["kids"],
    }


def test_drops_participation_hires_comedy_and_ancillaries():
    joined = " ".join(e.title for e in _programme())
    for dropped in ("Half Term", "Young Associates", "Choir", "Comedy", "Laugh Till You Drop",
                    "CASA", "Jawdance", "Kindrd", "Kromanti", "Pop Up", "Touch Tour",
                    "Q+A", "Secure My Booking"):
        assert dropped not in joined
    # Family Events in the participation programme are not shows.
    assert bh.categorize({"attribute_Genre": "Family Events",
                          "attribute_Season": "Creative Engagement"}) == []


def test_show_page_gives_ids_and_full_price():
    html = (FIXTURES / "brixton_house_show.html").read_text()
    ids = spk.embedded_ids(html)
    assert len(ids) == 16
    assert bh.page_price(html) == "£16"  # "Tickets: £16 / £12 concessions"
    events = _programme({PROVIDERS_PAGE: (ids, bh.page_price(html))})
    providers = [e for e in events if e.title == "Providers"]
    assert providers and all(e.source_url == PROVIDERS_PAGE and e.price == "£16" for e in providers)
    # Events without a page keep the Spektrix event page and the list price.
    baby = [e for e in events if e.title == "Baby"]
    assert all("ovalhouse/website/EventDetails.aspx" in e.source_url for e in baby)
