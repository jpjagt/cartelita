"""Tests for the jazzin.amsterdam multi-venue API source.

All tests run offline against a saved API response — no network access.
"""
from __future__ import annotations
import datetime as dt
import json
from collections import Counter
from pathlib import Path

import pytest

from cartelera.scrapers import REGISTRY, load_all
from cartelera.scrapers.jazzin_amsterdam import (
    SOURCE_SLUG,
    VENUES,
    parse_events,
    parse_price,
)

FIXTURES = Path(__file__).parent / "fixtures"
ITEMS = json.loads((FIXTURES / "jazzin_amsterdam_api.json").read_text())
EVENTS, UNKNOWN = parse_events(ITEMS)


def test_parses_most_of_the_feed():
    # ~600 raw items; the Muziekgebouw duplicates collapse, nothing else drops.
    assert len(EVENTS) > 450


def test_every_fixture_venue_is_whitelisted():
    assert UNKNOWN == set()


def test_every_event_is_complete_jazz_with_a_known_venue():
    slugs = {slug for slug, *_ in VENUES}
    for ev in EVENTS:
        assert ev.title
        assert isinstance(ev.start_date, dt.date)
        assert ev.source_url.startswith("http")
        assert ev.category_slugs == ["jazz"]
        assert ev.venue_slug in slugs
        assert ev.external_id


def test_times_are_parsed():
    assert sum(ev.start_time is not None for ev in EVENTS) / len(EVENTS) > 0.95


def test_external_ids_are_unique():
    counts = Counter(ev.external_id for ev in EVENTS)
    assert [k for k, n in counts.items() if n > 1] == []


def test_duplicate_listings_collapse_to_one_occurrence():
    keys = Counter((ev.venue_slug, ev.start_date, ev.start_time, ev.title.casefold()) for ev in EVENTS)
    assert max(keys.values()) == 1
    # The fixture lists one Muziekgebouw SANAM concert 5× under distinct ids.
    raw = [i for i in ITEMS if i["venue"] == "Muziekgebouw" and i["title"] == "SANAM"]
    assert len(raw) > len({(i["date"], i["time"]) for i in raw})


def test_venue_name_variants_merge():
    zojazz = [i for i in ITEMS if "bijlmerplein 888" in i["address"].casefold()]
    assert len({i["venue"] for i in zojazz}) > 1  # several spellings upstream
    ids = {str(i["id"]) for i in zojazz}
    assert {ev.venue_slug for ev in EVENTS if ev.external_id in ids} == {"zojazz-stage"}


def test_price_coverage_matches_the_source():
    # jazzin leaves ~1/3 of prices blank; every non-blank price must survive.
    with_price = sum(1 for i in ITEMS if (i["price"] or "").strip() not in ("", "€"))
    assert with_price / len(ITEMS) > 0.5
    priced = {ev.external_id for ev in EVENTS if ev.price}
    for i in ITEMS:
        if (i["price"] or "").strip() not in ("", "€") and str(i["id"]) in {e.external_id for e in EVENTS}:
            assert str(i["id"]) in priced


def test_unknown_venues_are_dropped_and_reported():
    item = dict(ITEMS[0], venue="Some New Café", id=1)
    events, unknown = parse_events([item])
    assert events == []
    assert unknown == {"Some New Café"}


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", None),
        ("€", None),
        ("free", "free"),
        ("0", "free"),
        ("€0", "free"),
        ("s.o.", "sold-out"),
        ("€13", "13€"),
        ("€19.5", "19,50€"),
        ("EUR 15.00", "15€"),
        ("15.00", "15€"),
        ("€12–€15", "15€"),           # < 2× spread: highest only
        ("€12.5–€25", "12,50–25€"),   # ≥ 2× spread: range
        ("6 / 12.5", "6–12,50€"),
        ("donatie", "donatie"),
    ],
)
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


def test_registered_as_amsterdam_jazz_source():
    load_all()
    _scraper, source = REGISTRY[SOURCE_SLUG]
    assert len(source.venues) == len(VENUES)
    for v in source.venues:
        assert v.city_slug == "amsterdam"
        assert [m.list_slug for m in v.list_memberships] == ["jazz"]
