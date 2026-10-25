"""Southbank Centre: artform listings + JSON-LD event pages (fixtures
captured 2026-10-25)."""

import datetime as dt
from pathlib import Path

from cartelera.scrapers import southbank_centre as sbc

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 25)
PAGES = ["alceu-valenca", "tarana", "now-not-now", "dvorak-violin-concerto-with-james-ehnes",
         "theres-a-bear-on-my-chair", "bob-dylan"]


def _pages():
    return [sbc.parse_event((FIXTURES / f"southbank_centre_{s}.html").read_text(), f"{sbc.SITE}/whats-on/{s}/")
            for s in PAGES]


def _by_slug():
    out = {}
    for e in sbc.build(_pages(), TODAY):
        out.setdefault(e.source_url.rstrip("/").rsplit("/", 1)[-1], []).append(e)
    return out


def test_listing_reads_primary_artform_and_pages():
    cards, pages = sbc.parse_listing((FIXTURES / "southbank_centre_listing_gigs.html").read_text(), sbc.listing_url("gigs"))
    assert "Literature & poetry" in cards.values()  # listed by the gigs filter, primary artform elsewhere
    assert cards[f"{sbc.SITE}/whats-on/alceu-valenca/"] == "Gigs"
    assert pages and all("artform-filter=gigs" in p for p in pages)


def test_categories_from_primary_artform_and_series():
    ev = _by_slug()
    assert ev["alceu-valenca"][0].category_slugs == ["pop"]
    assert ev["tarana"][0].category_slugs == ["jazz"]  # EFG London Jazz Festival series
    assert ev["now-not-now"][0].category_slugs == ["theater", "dance"]
    assert ev["dvorak-violin-concerto-with-james-ehnes"][0].category_slugs == ["classical"]
    assert ev["theres-a-bear-on-my-chair"][0].category_slugs == ["kids"]
    assert sbc.categories(sbc.EventPage("u", "t", "Literature & poetry", [])) == []


def test_one_event_per_performance_with_price_and_hall():
    ev = _by_slug()
    assert len(ev["now-not-now"]) == 2
    assert ev["alceu-valenca"][0].price == "£56" and ev["alceu-valenca"][0].annotations[0] == "Royal Festival Hall"
    assert ev["alceu-valenca"][0].start_time == dt.time(19, 30)
    events = [e for evs in ev.values() for e in evs]
    assert len({e.external_id for e in events}) == len(events)
    assert sum(e.price is not None for e in events) == len(events)


def test_free_drop_in_is_free_not_sold_out():
    assert ev_price("tarana") == "free"
    assert ev_price("bob-dylan") == "sold-out"


def ev_price(slug):
    return _by_slug()[slug][0].price
