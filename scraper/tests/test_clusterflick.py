"""Offline tests for the clusterflick multi-venue film source (saved,
trimmed data-transformed assets)."""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path

import pytest

from cartelera.scrapers import load_all
from cartelera.scrapers.clusterflick import (
    KEEP_CATEGORIES,
    SOURCE_SLUG,
    VENUE_ASSETS,
    VENUES,
    ClusterflickScraper,
    check_release_age,
    parse_asset,
)

FIXTURE = Path(__file__).parent / "fixtures" / "clusterflick_assets.json"
TODAY = dt.date(2026, 10, 25)
ASSET_TO_SLUG = {a: v.slug for a, v in VENUE_ASSETS}


def _assets() -> dict[str, list[dict]]:
    return json.loads(FIXTURE.read_text())


def _events(asset: str):
    return parse_asset(_assets()[asset], ASSET_TO_SLUG[asset], TODAY)


def test_only_screening_categories_are_kept():
    items = _assets()["bfi.org.uk-southbank"]
    cats = Counter(i["category"] for i in items)
    assert cats["talk"] and cats["tv"] and cats["quiz"]  # fixture covers the drops
    kept_titles = {i["title"] for i in items if i["category"] in KEEP_CATEGORIES}
    dropped_titles = {i["title"] for i in items if i["category"] not in KEEP_CATEGORIES}
    events = _events("bfi.org.uk-southbank")
    titles = {e.title for e in events}
    assert titles <= kept_titles
    assert not titles & dropped_titles
    assert all(e.category_slugs == ["film"] for e in events)
    assert all(e.venue_slug == "bfi-southbank" for e in events)


def test_one_event_per_performance_in_london_time():
    items = _assets()["princecharlescinema.com"]
    item = next(i for i in items if i["url"].endswith("/7260457/2001-a-space-odyssey"))
    events = [e for e in _events("princecharlescinema.com") if e.source_url == item["url"]]
    assert len(events) == len(item["performances"])
    # 1798489200000 ms = 2026-12-28 20:20 UTC = 20:20 GMT (winter)
    first = min(events, key=lambda e: (e.start_date, e.start_time))
    assert (first.start_date, first.start_time) == (dt.date(2026, 12, 28), dt.time(20, 20))
    assert first.title == "2001 : A Space Odyssey"  # the venue's raw title, not TMDB's
    assert "70mm" in first.annotations
    assert first.price is None and first.description is None and first.image_url is None


def test_bst_conversion():
    # A summer timestamp: London is UTC+1 (BST).
    item = {"category": "movie", "title": "X", "url": "https://x/1",
            "performances": [{"time": 1782838800000, "bookingUrl": "https://x/b"}]}  # 2026-06-30 17:00Z
    (ev,) = parse_asset([item], "rio-cinema", dt.date(2026, 6, 1))
    assert (ev.start_date, ev.start_time) == (dt.date(2026, 6, 30), dt.time(18, 0))


def test_past_performances_dropped():
    for asset in _assets():
        assert all(e.start_date >= TODAY for e in _events(asset))
    items = _assets()["princecharlescinema.com"]
    assert any(p["time"] < 1792882800000 for i in items for p in i["performances"])


def test_external_ids_unique_per_venue_even_when_booking_url_is_per_film():
    for asset in _assets():
        events = _events(asset)
        ids = [e.external_id for e in events]
        assert len(ids) == len(set(ids)), asset
    # Ciné Lumière lists one screening under two items: emitted once.
    items = _assets()["institut-francais.org.uk"]
    dup_items = [i for i in items if i["title"] == "Le Plein de Super"]
    assert len(dup_items) == 2
    events = [e for e in _events("institut-francais.org.uk") if e.title == "Le Plein de Super"]
    raw = {(p["bookingUrl"], p["time"]) for i in dup_items for p in i["performances"]
           if dt.datetime.fromtimestamp(p["time"] / 1000, dt.timezone.utc).date() >= TODAY}
    assert len(events) == len(raw)


def test_sold_out_becomes_price_sold_out():
    events = _events("princecharlescinema.com")
    assert any(e.price == "sold-out" for e in events)
    assert all(e.price in (None, "sold-out") for e in events)


def test_notes_format_accessibility_become_annotations():
    pcc = _events("princecharlescinema.com")
    assert any("Sing Along" in e.annotations for e in pcc)
    curzon = _events("curzon.com-bloomsbury")
    assert any("Programmed by Bertha Dochouse" in e.annotations for e in curzon)
    assert any({"subtitled", "audio-described", "hard-of-hearing"} & set(e.annotations)
               for e in curzon)
    # multi-line notes split into separate labels, no empties
    for e in pcc + curzon:
        assert all(a and "\n" not in a for a in e.annotations)
        assert len(e.annotations) == len(set(e.annotations))


def test_unknown_category_dropped():
    item = {"category": "karaoke", "title": "X", "url": "https://x/1",
            "performances": [{"time": 1798489200000, "bookingUrl": "https://x/b"}]}
    assert parse_asset([item], "rio-cinema", TODAY) == []


def test_release_age_guard():
    now = dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc)
    check_release_age("2026-10-24T16:40:51Z", now)
    with pytest.raises(RuntimeError):
        check_release_age("2026-10-20T16:40:51Z", now)


def test_missing_assets_tolerated_until_most_fail(monkeypatch):
    data = _assets()
    scraper = ClusterflickScraper()
    monkeypatch.setattr(scraper, "_check_release", lambda client: None)
    # only the 4 fixture assets answer: most failed -> the source fails
    monkeypatch.setattr(scraper, "_fetch_asset",
                        lambda client, asset: data.get(asset) if asset in data else None)
    with pytest.raises(RuntimeError, match="assets failed"):
        scraper.scrape()
    present = {a for a, _ in VENUE_ASSETS[: len(VENUE_ASSETS) // 2 + 1]}
    monkeypatch.setattr(scraper, "_fetch_asset",
                        lambda client, asset: data.get(asset, []) if asset in present else None)
    events = scraper.scrape()  # a minority failed: the rest still emit
    assert {e.venue_slug for e in events} <= {ASSET_TO_SLUG[a] for a in present}


OWNED_ELSEWHERE = {
    "barbican", "kiln-theatre", "rich-mix", "cafe-oto", "cadogan-hall", "conway-hall",
    "earth-hackney", "bush-theatre", "dalston-superstore", "jw3",
}


def test_registered_as_whitelist_source_with_unique_slugs():
    registry = load_all()
    _scraper, source = registry[SOURCE_SLUG]
    assert all(v.city_slug == "london" for v in source.venues)
    assert all(v.category_slugs == ["film"] for v in source.venues)
    assert all(v.lat is not None for v in source.venues)
    assert not {v.slug for v in VENUES} & OWNED_ELSEWHERE
    assert len({a for a, _ in VENUE_ASSETS}) == len(VENUE_ASSETS)
    owners: dict[str, str] = {}
    for slug, (_s, src) in registry.items():
        for v in src.venues:
            assert v.slug not in owners or owners[v.slug] == slug, v.slug
            owners[v.slug] = slug
