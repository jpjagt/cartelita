"""Offline tests for the jazz010.live multi-venue source (saved fixtures)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from cartelera.scrapers import load_all
from cartelera.scrapers.jazz010 import (
    ALIASES,
    EXCLUDED,
    SOURCE_SLUG,
    VENUES,
    build_event,
    parse_detail,
    parse_listing_page,
    parse_price,
    parse_timestamp,
    select_cards,
)

FIXTURES = Path(__file__).parent / "fixtures"
PAGES = {
    dt.date(2026, 10, 14): FIXTURES / "jazz010_events_2026-10-14.html",
    dt.date(2026, 10, 28): FIXTURES / "jazz010_events_2026-10-28.html",
}
DETAIL_PREFIX = "jazz010_event_"


def _details() -> dict[str, dict]:
    return {
        p.stem[len(DETAIL_PREFIX):]: parse_detail(p.read_text())
        for p in FIXTURES.glob(f"{DETAIL_PREFIX}*.html")
    }


def _all_cards() -> list[dict]:
    cards = []
    for start, path in PAGES.items():
        cards.extend(parse_listing_page(path.read_text(), start)[0])
    return cards


def _events():
    details = _details()
    events = [build_event(c, details.get(c["slug"])) for c in select_cards(_all_cards())]
    return [e for e in events if e is not None]


def test_listing_page_parses_main_list_and_next_link():
    cards, next_start = parse_listing_page(PAGES[dt.date(2026, 10, 14)].read_text(), dt.date(2026, 10, 14))
    assert next_start == dt.date(2026, 10, 28)
    assert len(cards) >= 20
    for c in cards:
        assert dt.date(2026, 10, 14) <= c["start_date"] <= dt.date(2026, 10, 28)
        assert c["title"] and c["venue_name"]
    # The regional "IN DE BUURT" block (Den Haag, Dordrecht) is not parsed.
    names = {c["venue_name"] for c in cards}
    assert not any("Den Haag" in n or "Dordrecht" in n for n in names)
    assert "Vrijmoed" in names


def test_timestamp_with_and_without_time_and_year_rollover():
    assert parse_timestamp("wo 14 oktober 19:30", dt.date(2026, 10, 14)) == (
        dt.date(2026, 10, 14), dt.time(19, 30))
    assert parse_timestamp("wo 21 oktober", dt.date(2026, 10, 14)) == (dt.date(2026, 10, 21), None)
    assert parse_timestamp("vr 8 januari 20:30", dt.date(2026, 12, 30))[0] == dt.date(2027, 1, 8)


def test_boundary_day_overlap_is_deduped():
    cards = _all_cards()
    ids = [e.external_id for e in _events()]
    assert len(ids) == len(set(ids))
    # Dizzy's 28 Oct gig is on both pages, but becomes one event.
    raw = [c for c in cards if c["slug"] == "dizzy-hammond-organ-jazz-night-2026-10-28"]
    assert len(raw) == 2
    assert sum(1 for e in _events() if e.title == "Hammond Organ Jazz night") == 1


def test_only_whitelisted_venues_emitted():
    events = _events()
    assert len(events) >= 30
    slugs = {v.slug for v in VENUES}
    assert {e.venue_slug for e in events} <= slugs
    # Owned elsewhere / outside Rotterdam / curated out: present in the raw
    # listing, never emitted.
    raw_names = {c["venue_name"] for c in _all_cards()}
    for name in ("LantarenVenster", "de Doelen", "Café LaBru", "BIRD"):
        assert name in raw_names
    for e in events:
        assert e.category_slugs == ["jazz"]
        assert e.source_url.startswith("https://jazz010.live/event/")
        assert "@" in e.external_id


def test_every_whitelisted_alias_points_at_a_venue_and_no_overlap_with_excluded():
    slugs = {v.slug for v in VENUES}
    assert set(ALIASES.values()) == slugs
    assert not set(ALIASES) & EXCLUDED


def test_price_parsing():
    assert parse_price("TICKETS - € 7,50") == "7,50€"
    assert parse_price("TICKETS - € 45,--") == "45€"
    assert parse_price("TICKETS - € 18,-") == "18€"
    assert parse_price("TICKETS -") is None
    assert parse_price(None) is None


def test_detail_fields_flow_into_events():
    events = _events()
    jadi = next(e for e in events if e.external_id.startswith("vrijmoed-jadi-peperzak"))
    assert jadi.price == "7,50€"
    assert jadi.start_time == dt.time(19, 30)
    assert jadi.venue_slug == "vrijmoed"
    assert "Codarts" in jadi.description and "Bezetting: " in jadi.description
    assert "Jadi Peperzak (gitaar)" in jadi.description
    assert jadi.image_url.startswith("https://jazz010.live/image/")

    lucy = next(e for e in events if "Lucy Woodward" in e.title)
    assert lucy.price == "18€" and lucy.venue_slug == "de-fruitvis"

    # "TICKETS -" without an amount: price unknown, not guessed.
    flink = next(e for e in events if e.title.startswith("FLiNK"))
    assert flink.price is None

    # A listing without a time.
    bakooter = next(e for e in events if e.title == "BaKooTer")
    assert bakooter.start_time is None and bakooter.external_id.endswith("T" + "none")


def test_free_and_sold_out_flags_from_listing():
    card = {
        "venue_name": "Dizzy", "title": "x", "slug": "dizzy-x", "start_date": dt.date(2026, 11, 1),
        "start_time": dt.time(21, 0), "free": False, "sold_out": True, "tip": True,
    }
    ev = build_event(card, {"ticket": "TICKETS - € 20,--", "organiser": "Dizzy"})
    assert ev.price == "sold-out"
    assert ev.annotations == ["tip"]
    ev = build_event({**card, "sold_out": False, "free": True}, None)
    assert ev.price == "free"


def test_organiser_series_becomes_annotation():
    d = parse_detail((FIXTURES / "jazz010_event_crossover-insomnia-2026-11-14.html").read_text())
    card = {
        "venue_name": "Hillegondakerk", "title": "INSOMNIA", "slug": "crossover-insomnia-2026-11-14",
        "start_date": dt.date(2026, 11, 14), "start_time": dt.time(20, 0),
        "free": False, "sold_out": False, "tip": False,
    }
    ev = build_event(card, d)
    assert ev.venue_slug == "hillegondakerk"
    assert ev.annotations == ["Cross Over Hillegonda"]
    assert ev.description


def test_registered_as_whitelist_source_with_unique_slugs():
    registry = load_all()
    _scraper, source = registry[SOURCE_SLUG]
    assert all(v.city_slug == "rotterdam" for v in source.venues)
    owners: dict[str, str] = {}
    for slug, (_s, src) in registry.items():
        for v in src.venues:
            assert v.slug not in owners or owners[v.slug] == slug, v.slug
            owners[v.slug] = slug
