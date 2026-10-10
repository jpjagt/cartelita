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
    CALENDARS,
    SOURCE_SLUG,
    VENUES,
    parse_events,
    parse_price,
    unlisted_categories,
)

FIXTURES = Path(__file__).parent / "fixtures"
# {category slug: [API event objects]}, every page of each used calendar.
BY_CATEGORY = json.loads((FIXTURES / "jazzin_amsterdam_api.json").read_text())
PAIRS = [(cat, item) for cat, items in BY_CATEGORY.items() for item in items]
ITEMS = [item for _cat, item in PAIRS]
EVENTS, UNKNOWN = parse_events(PAIRS)
EXCLUDED = {"Grote Zaal", "Kleine Zaal", "Comedytrain - Westergas - Grote Zaal",
            "Comedytrain - Westergas - Kleine Zaal", "Stadsgehoorzaal Leiden",
            "TivoliVredenburg", "De Kulturele Raad", "Papagenohuis",
            "Theater Het Klooster Woerden",
            # alternative calendar: own scraper / closed venue / non-venues
            "Filmhuis Cavia", "Nassaukerk", "Bar Bario", "Amsterdam",
            "Buikslotermeerplein", "Op de brug", "Jan van Galenstraat A10 snelweg",
            "Fossil Free Culture NL"}


def test_fixture_covers_every_calendar():
    assert set(BY_CATEGORY) == set(CALENDARS.values())


def test_parses_most_of_the_feed():
    # ~6,700 raw items; duplicates and the excluded venues drop out.
    assert len(EVENTS) > 5300


def test_only_deliberately_excluded_venues_are_dropped():
    assert UNKNOWN == EXCLUDED


def test_every_event_is_complete_with_a_known_venue():
    slugs = {slug for slug, *_ in VENUES}
    for ev in EVENTS:
        assert ev.title
        assert isinstance(ev.start_date, dt.date)
        assert ev.source_url.startswith("http")
        assert set(ev.category_slugs) <= set(CALENDARS.values())
        assert ev.venue_slug in slugs
        assert ev.external_id


def test_every_category_is_well_represented():
    counts = Counter(c for ev in EVENTS for c in ev.category_slugs)
    for cat in CALENDARS.values():
        assert counts[cat] > 300, cat
    assert counts["alternative"] > 700


def test_venue_categories_cover_the_fixture():
    assert unlisted_categories(EVENTS) == set()


def test_cross_calendar_duplicates_merge_categories():
    # A Muziekgebouw/Concertgebouw concert listed in both jazz and classical
    # becomes one event carrying both categories.
    multi = [ev for ev in EVENTS if len(ev.category_slugs) > 1]
    assert len(multi) > 50
    assert any(set(ev.category_slugs) == {"jazz", "classical"} for ev in multi)


def test_times_are_parsed():
    assert sum(ev.start_time is not None for ev in EVENTS) / len(EVENTS) > 0.95


def test_external_ids_are_unique():
    counts = Counter(ev.external_id for ev in EVENTS)
    assert [k for k, n in counts.items() if n > 1] == []


def test_duplicate_listings_collapse_to_one_occurrence():
    keys = Counter((ev.venue_slug, ev.start_date, ev.start_time, ev.title.casefold()) for ev in EVENTS)
    assert max(keys.values()) == 1
    # The fixture lists one Muziekgebouw SANAM concert 5× under distinct ids.
    raw = [i for i in BY_CATEGORY["jazz"] if i["venue"] == "Muziekgebouw" and i["title"] == "SANAM"]
    assert len(raw) > len({(i["date"], i["time"]) for i in raw})


def test_alternative_calendar_spans_diy_venues():
    alt = [ev for ev in EVENTS if "alternative" in ev.category_slugs]
    venues = {ev.venue_slug for ev in alt}
    assert {"ot301", "nieuwland", "occii", "tolhuistuin", "de-nieuwe-anita", "volkshotel"} <= venues
    assert len(venues) > 35


def test_same_address_aliases_merge_across_feeds():
    # Plantage Dok's own feed and squatradar ("Dokhuis Galerie") list the same
    # weekly DOK Night; it merges to one occurrence at one venue.
    raw = [i for i in BY_CATEGORY["alternative"]
           if "plantage doklaan 8" in i["address"].casefold()]
    assert len({i["venue"] for i in raw}) > 1
    ids = {str(i["id"]) for i in raw}
    kept = [ev for ev in EVENTS if ev.external_id in ids]
    assert {ev.venue_slug for ev in kept} == {"plantage-dok"}
    assert len(kept) < len(raw)


def test_source_urls_have_no_stray_quotes():
    assert not [ev.source_url for ev in EVENTS if ev.source_url.endswith(("'", '"'))]


def test_venue_name_variants_merge():
    zojazz = [i for i in ITEMS if "bijlmerplein 888" in i["address"].casefold()]
    assert len({i["venue"] for i in zojazz}) > 1  # several spellings upstream
    ids = {str(i["id"]) for i in zojazz}
    assert {ev.venue_slug for ev in EVENTS if ev.external_id in ids} == {"zojazz-stage"}


def test_price_coverage_matches_the_source():
    # jazzin leaves many prices blank (all film ones, a bare "€"/"EUR"); every non-blank price
    # on a kept event must survive.
    jazz = BY_CATEGORY["jazz"]
    with_price = sum(1 for i in jazz if (i["price"] or "").strip() not in ("", "€"))
    assert with_price / len(jazz) > 0.5
    kept = {e.external_id for e in EVENTS}
    priced = {ev.external_id for ev in EVENTS if ev.price}
    for i in ITEMS:
        if (i["price"] or "").strip() not in ("", "€", "EUR") and str(i["id"]) in kept:
            assert str(i["id"]) in priced


def test_status_markers_in_titles():
    base = dict(ITEMS[0], venue="Bimhuis", price="€13")
    events, _ = parse_events([
        ("jazz", dict(base, id=1, title="Joan As Police Woman (sold out)")),
        ("jazz", dict(base, id=2, title="Babs [CANCELED]", time="21:00:00")),
    ])
    assert [(ev.title, ev.price) for ev in events] == [("Joan As Police Woman", "sold-out")]


def test_unknown_venues_are_dropped_and_reported():
    item = dict(ITEMS[0], venue="Some New Café", id=1)
    events, unknown = parse_events([("jazz", item)])
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
        ("uitverkocht/nietbeschikbaar", "sold-out"),
        ("€13", "13€"),
        ("€19.5", "19,50€"),
        ("EUR 15.00", "15€"),
        ("15.00", "15€"),
        ("€12–€15", "15€"),           # < 2× spread: highest only
        ("€12.5–€25", "12,50–25€"),   # ≥ 2× spread: range
        ("6 / 12.5", "6–12,50€"),
        ("donatie", "donatie"),
        ("tips", "tips"),
        ("EUR ", None),
        ("€Sliding scale donation", "Sliding scale donation"),
        ("€Donation 5-40", "5–40€"),
    ],
)
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


def test_registered_as_amsterdam_source_with_whitelisted_lists():
    load_all()
    _scraper, source = REGISTRY[SOURCE_SLUG]
    assert len(source.venues) == len(VENUES)
    for v in source.venues:
        assert v.city_slug == "amsterdam"
        assert v.list_memberships
        for m in v.list_memberships:
            assert m.whitelist_category_slug == m.list_slug
            assert m.list_slug in v.category_slugs
