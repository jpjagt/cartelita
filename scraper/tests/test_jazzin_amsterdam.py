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
    DENIED,
    DENIED_FEEDS,
    SOURCE_SLUG,
    VENUES,
    VENUE_BY_KEY,
    _venue_key,
    occurrence_key,
    parse_events,
    parse_price,
    resolve_venue,
    slugify,
)
from cartelera.run import unlisted_categories

FIXTURES = Path(__file__).parent / "fixtures"
# {category slug: [API event objects]}, every page of each used calendar.
BY_CATEGORY = json.loads((FIXTURES / "jazzin_amsterdam_api.json").read_text())
PAIRS = [(cat, item) for cat, items in BY_CATEGORY.items() for item in items]
ITEMS = [item for _cat, item in PAIRS]
EVENTS, DISCOVERED, DENIED_NAMES = parse_events(PAIRS)


def ext_id(item: dict) -> str | None:
    """The external_id the scraper derives for one raw API item (None when
    the item is dropped)."""
    evs, _, _ = parse_events([("jazz", item)])
    return evs[0].external_id if evs else None
# Denied by name, or (the Comedytrain halls) by their toomler feed.
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


def test_only_deliberately_denied_venues_are_dropped():
    assert DENIED_NAMES == EXCLUDED
    # Every other venue in the fixture is covered by an override.
    assert DISCOVERED == []


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
    # The source extends its venues' categories at run time anyway; the
    # VENUES table still covers the fixture.
    by_venue: dict = {}
    for ev in EVENTS:
        by_venue.setdefault(ev.venue_slug, []).append(ev)
    assert unlisted_categories(REGISTRY[SOURCE_SLUG][1], by_venue) == set()


def test_source_extends_venue_categories():
    assert REGISTRY[SOURCE_SLUG][1].extends_venue_categories is True


def test_cross_calendar_duplicates_merge_categories():
    # A Muziekgebouw/Concertgebouw concert listed in both jazz and classical
    # becomes one event carrying both categories.
    multi = [ev for ev in EVENTS if len(ev.category_slugs) > 1]
    assert len(multi) > 50
    assert any(set(ev.category_slugs) == {"jazz", "classical"} for ev in multi)


def test_times_are_parsed():
    assert sum(ev.start_time is not None for ev in EVENTS) / len(EVENTS) > 0.95


def test_external_ids_are_unique_per_venue():
    # The upsert dedups on (venue, external_id); content keys may repeat
    # across venues (one touring title at the same time in two places).
    counts = Counter((ev.venue_slug, ev.external_id) for ev in EVENTS)
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
    ids = {ext_id(i) for i in raw}
    kept = [ev for ev in EVENTS if ev.external_id in ids and ev.venue_slug == "plantage-dok"]
    assert {VENUE_BY_KEY[_venue_key(i["venue"])] for i in raw} == {"plantage-dok"}
    assert len(kept) < len(raw)


def test_source_urls_have_no_stray_quotes():
    assert not [ev.source_url for ev in EVENTS if ev.source_url.endswith(("'", '"'))]


def test_venue_name_variants_merge():
    zojazz = [i for i in ITEMS if "bijlmerplein 888" in i["address"].casefold()]
    assert len({i["venue"] for i in zojazz}) > 1  # several spellings upstream
    assert {VENUE_BY_KEY[_venue_key(i["venue"])] for i in zojazz} == {"zojazz-stage"}
    ids = {ext_id(i) for i in zojazz}
    assert any(ev.venue_slug == "zojazz-stage" for ev in EVENTS if ev.external_id in ids)


def test_price_coverage_matches_the_source():
    # jazzin leaves many prices blank (all film ones, a bare "€"/"EUR"); every non-blank price
    # on a kept event must survive.
    jazz = BY_CATEGORY["jazz"]
    with_price = sum(1 for i in jazz if (i["price"] or "").strip() not in ("", "€"))
    assert with_price / len(jazz) > 0.5
    # Duplicate listings merge into the first-listed (lowest id) item's event,
    # whose price must survive.
    priced = {(ev.venue_slug, ev.external_id) for ev in EVENTS if ev.price}
    first: dict[tuple, dict] = {}
    for i in sorted(ITEMS, key=lambda i: i["id"]):
        slug = VENUE_BY_KEY.get(_venue_key((i["venue"] or "").strip()))
        key = (slug, ext_id(i))
        if slug and key[1]:
            first.setdefault(key, i)
    for key, i in first.items():
        if (i["price"] or "").strip() not in ("", "€", "EUR"):
            assert key in priced


def test_status_markers_in_titles():
    base = dict(ITEMS[0], venue="Bimhuis", price="€13")
    events, _, _ = parse_events([
        ("jazz", dict(base, id=1, title="Joan As Police Woman (sold out)")),
        ("jazz", dict(base, id=2, title="Babs [CANCELED]", time="21:00:00")),
    ])
    assert [(ev.title, ev.price) for ev in events] == [("Joan As Police Woman", "sold-out")]


# --- opt-out: discovered venues ---------------------------------------------------

def _item(venue: str, id_: int, **kw) -> dict:
    base = dict(ITEMS[0], venue=venue, id=id_, title=f"Gig {id_}", date="2026-11-03",
                time="20:30:00", price="€10", site="https://example.org/gig",
                address="Somestraat 1, 1011 AA Amsterdam", source="submit")
    base.update(kw)
    return base


def test_unknown_venue_is_discovered():
    events, venues, denied = parse_events([
        ("jazz", _item("  Café  de Muurbloem ", 1, address="Bloemgracht 170, 1015 TV Amsterdam")),
        ("classical", _item("Café de Muurbloem", 2, address="Bloemgracht 170, 1015 TV Amsterdam")),
        ("jazz", _item("café de muurbloem", 3, address="Amsterdam")),
    ])
    assert denied == set()
    assert {ev.venue_slug for ev in events} == {"cafe-de-muurbloem"}
    assert len(events) == 3
    [v] = venues
    assert v.slug == "cafe-de-muurbloem"
    assert v.name == "Café de Muurbloem"            # most common spelling, trimmed
    assert v.address == "Bloemgracht 170, 1015 TV Amsterdam"  # "Amsterdam" alone ignored
    assert v.city_slug == "amsterdam"
    assert v.category_slugs == ["jazz", "classical"]  # calendar order
    assert [(m.list_slug, m.whitelist_category_slug) for m in v.list_memberships] == [
        ("jazz", "jazz"), ("classical", "classical")]


def test_discovered_venue_with_only_a_city_address_has_none():
    _, [v], _ = parse_events([("pop", _item("Felix Meritis", 1, address=", Amsterdam"))])
    assert v.address is None


def test_denied_names_and_feeds_produce_no_venue_or_events():
    events, venues, denied = parse_events([
        ("alternative", _item("Amsterdam", 1)),
        ("alternative", _item("  op  de brug", 2)),           # key-normalized match
        ("theater", _item("Comedytrain - Westergas - Grote Zaal", 3, source="toomler")),
        ("classical", _item("TivoliVredenburg", 4)),
    ])
    assert events == [] and venues == []
    assert denied == {"Amsterdam", "op de brug", "Comedytrain - Westergas - Grote Zaal",
                      "TivoliVredenburg"}
    assert "toomler" in DENIED_FEEDS
    assert all(reason for reason in DENIED.values())


def test_aliases_still_merge_into_overrides():
    events, venues, _ = parse_events([
        ("jazz", _item("Roode Bioscoop", 1)),
        ("classical", _item("Gelvinck Pianola Museum", 2)),
        ("classical", _item("Ensemblezaal, CvA", 3)),
        ("theater", _item("Het Verbond - Café", 4)),
    ])
    assert venues == []
    assert [ev.venue_slug for ev in events] == [
        "de-roode-bioscoop", "pianola-museum", "conservatorium-van-amsterdam", "het-verbond"]


def test_no_override_alias_is_denied_and_slugs_are_unique():
    alias_keys = set(VENUE_BY_KEY)
    assert not alias_keys & {_venue_key(n) for n in DENIED}
    slugs = [slug for slug, *_ in VENUES]
    assert len(slugs) == len(set(slugs))


@pytest.mark.parametrize("name,slug", [
    ("Joe's Garage", "joes-garage"),
    ("Café Czaar", "cafe-czaar"),
    ("ITA | Internationaal Theater", "ita-internationaal-theater"),
    ("The Brokers Bar (Beurs van Berlage)", "the-brokers-bar-beurs-van-berlage"),
    ("Dick & Dick", "dick-dick"),
    ("Sociëteit ‘De Kring’", "societeit-de-kring"),
])
def test_slugify(name, slug):
    assert slugify(name) == slug


def test_resolve_venue():
    assert resolve_venue("ZOjazz Stage") == "zojazz-stage"
    assert resolve_venue("Frascati") == "frascati"
    assert resolve_venue("Bar Bario") is None
    assert resolve_venue("") is None
    assert resolve_venue("!!!") is None


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


def test_external_id_is_content_derived_and_stable_across_relisted_ids():
    # jazzin re-scrapes nightly and hands out new numeric ids; the same
    # occurrence must keep its key regardless.
    base = dict(ITEMS[0], venue="Bimhuis", title="Joan  As Police Woman ",
                date="2026-11-03", time="20:30:00")
    a, _, _ = parse_events([("jazz", dict(base, id=111))])
    b, _, _ = parse_events([("jazz", dict(base, id=999, title="joan as police woman"))])
    assert a[0].external_id == b[0].external_id
    assert a[0].external_id == occurrence_key(
        dt.date(2026, 11, 3), dt.time(20, 30), "Joan As Police Woman")
    assert len(a[0].external_id) == 16 and not a[0].external_id.isdigit()
    # a sold-out marker added later doesn't change it either
    c, _, _ = parse_events([("jazz", dict(base, id=5, title="Joan As Police Woman (sold out)"))])
    assert c[0].external_id == a[0].external_id
    # a different date or time is a different occurrence
    d, _, _ = parse_events([("jazz", dict(base, id=6, time="22:00:00"))])
    assert d[0].external_id != a[0].external_id


def test_occurrence_key_without_time():
    assert occurrence_key(dt.date(2026, 1, 2), None, "X") != occurrence_key(
        dt.date(2026, 1, 2), dt.time(0, 0), "X")
