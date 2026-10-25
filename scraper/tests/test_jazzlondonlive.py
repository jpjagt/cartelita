"""Offline tests for the jazzlondonlive.com multi-venue source (saved fixtures)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from cartelera.scrapers import load_all
from cartelera.scrapers.jazzlondonlive import (
    ALIASES,
    BASE_URL,
    EXCLUDED,
    SOURCE_SLUG,
    VENUES,
    events_from_rows,
    months_to_fetch,
    parse_dates_page,
    parse_month_index,
    parse_price,
    parse_venue_page,
    rows_from_venue_pages,
    select_venues,
    whitelisted_rows,
)

FIXTURES = Path(__file__).parent / "fixtures"
OCT_1 = dt.date(2026, 10, 1)
OCT_24 = dt.date(2026, 10, 24)
VENUE_IDS = {2: "606-club", 5: "the-archduke", 20: "clocktower-cafe-croydon",
             59: "ronnie-scotts", 70: "toulouse-lautrec", 75: "vortex-jazz-club"}


def _index():
    return parse_month_index((FIXTURES / "jazzlondonlive_month_2026-10.html").read_text())


def _dates_rows():
    return parse_dates_page((FIXTURES / "jazzlondonlive_jazz-dates_2026-10.html").read_text())


def _venue_rows():
    return rows_from_venue_pages([
        (slug, f"{BASE_URL}/venue/2026/10/{vid}",
         (FIXTURES / f"jazzlondonlive_venue_2026-10_{vid}.html").read_text())
        for vid, slug in VENUE_IDS.items()
    ])


def test_month_index_lists_venues_and_whitelist_selects():
    index = _index()
    assert len(index) >= 70
    names = {n for n, _p in index}
    assert "Vortex Jazz Club, Dalston" in names and "The Bear Club, Luton" in names
    kept = dict(select_venues(index))
    assert kept["vortex-jazz-club"] == "/venue/2026/10/75"
    assert kept["606-club"] == "/venue/2026/10/2"
    assert "pizzaexpress-jazz-club-soho" not in kept
    assert len(kept) >= 30
    # Every venue on the October index is classified (whitelist or excluded).
    unknown = [n for n in names
               if " ".join(n.split()).casefold() not in ALIASES
               and " ".join(n.split()).casefold() not in EXCLUDED]
    assert unknown == []


def test_empty_next_month_index():
    assert parse_month_index((FIXTURES / "jazzlondonlive_month_2026-11.html").read_text()) == []
    assert months_to_fetch(dt.date(2026, 10, 25)) == [(2026, 10), (2026, 11)]
    assert months_to_fetch(dt.date(2026, 12, 3)) == [(2026, 12), (2027, 1)]


def test_dates_page_rows():
    rows = _dates_rows()
    assert len(rows) == 177
    gab = next(r for r in rows if r["title"] == "The GAB Trio")
    assert gab["venue"] == "Toulouse Lautrec, Kennington"
    assert gab["start_date"] == OCT_24 and gab["start_time"] == dt.time(20, 30)
    assert gab["price_text"] == "£21.50" and gab["note"] == "Live Show"
    ronnie = next(r for r in rows if r["venue"] == "Ronnie Scott's, Soho")
    assert ronnie["price_text"] == ""


def test_current_month_events_whitelist_and_fields():
    rows = whitelisted_rows(_dates_rows(), _index())
    events = events_from_rows(rows, OCT_24)
    slugs = {e.venue_slug for e in events}
    assert slugs <= {v.slug for v in VENUES}
    assert "ronnie-scotts" in slugs and "vortex-jazz-club" in slugs
    raw_venues = {r["venue"] for r in _dates_rows()}
    for name in ("Blue Note London", "PizzaExpress Jazz Club, Soho", "The Bear Club, Luton",
                 "Boisdale of Belgravia"):
        assert name in raw_venues
    assert all(e.category_slugs == ["jazz"] for e in events)
    ids = [(e.venue_slug, e.external_id) for e in events]
    assert len(ids) == len(set(ids))

    gab = next(e for e in events if e.title == "The GAB Trio")
    assert gab.venue_slug == "toulouse-lautrec" and gab.price == "£21.50"
    assert gab.annotations == ["Live Show"]
    assert gab.source_url == "https://toulouselautrec.co.uk/whats-on/the-gab-trio/"
    assert gab.external_id == "2026-10-24T2030@https://toulouselautrec.co.uk/whats-on/the-gab-trio/"
    # A longer editor's note becomes the description.
    posk = next(e for e in events if e.title.startswith("Ruta Di"))
    assert posk.description and "2 stes" in posk.description and posk.annotations == []
    # Junk links ("http://") fall back to the venue's guide page.
    clock = [e for e in events if e.venue_slug == "clocktower-cafe-croydon"]
    assert clock and all(e.source_url == f"{BASE_URL}/venue/2026/10/20" for e in clock)


def test_venue_pages_fold_note_into_title_but_keep_the_same_key():
    name, rows = parse_venue_page((FIXTURES / "jazzlondonlive_venue_2026-10_70.html").read_text())
    assert name == "Toulouse Lautrec, Kennington"
    assert any(r["title"] == "The GAB Trio (Live Show)" for r in rows)
    via_pages = {e.external_id: e for e in events_from_rows(_venue_rows(), OCT_24)
                 if e.venue_slug == "toulouse-lautrec"}
    via_dates = {e.external_id: e for e in events_from_rows(
        whitelisted_rows(_dates_rows(), _index()), OCT_24) if e.venue_slug == "toulouse-lautrec"}
    # Same occurrences, same keys, whichever page they come from (titles differ).
    assert set(via_pages) == set(via_dates)


def test_venue_pages_residencies_and_prices():
    events = events_from_rows(_venue_rows(), OCT_1)
    ronnie = [e for e in events if e.venue_slug == "ronnie-scotts"]
    assert len(ronnie) == 137
    mcbride = [e for e in ronnie if e.title == "Christian McBride & Ursa Major"]
    assert len(mcbride) >= 2 and len({e.source_url for e in mcbride}) == 1
    assert len({e.external_id for e in mcbride}) == len(mcbride)
    assert all(e.price is None for e in ronnie)  # the guide has no Ronnie's prices
    vortex = [e for e in events if e.venue_slug == "vortex-jazz-club"]
    assert len(vortex) == 37  # one generic link for all: date+time keeps them apart
    first = next(e for e in vortex if e.start_date == OCT_1)
    assert first.title == "Rick Simpson's Future Myth" and first.price == "£19"
    archduke = [e for e in events if e.venue_slug == "the-archduke"]
    assert archduke and all(e.price == "free" for e in archduke)


def test_past_rows_dropped_and_key_clash_resolved():
    events = events_from_rows(_venue_rows(), dt.date(2026, 10, 25))
    assert events and all(e.start_date >= dt.date(2026, 10, 25) for e in events)
    row = {"start_date": OCT_24, "start_time": dt.time(20), "price_text": "", "href": "http://",
           "note": "", "title": "A"}
    clash = events_from_rows([("syp", "u", row), ("syp", "u", {**row, "title": "B"}),
                              ("syp", "u", dict(row))], OCT_24)
    assert [e.external_id for e in clash] == ["2026-10-24T2000", "2026-10-24T2000#B"]


def test_price_normalization():
    assert parse_price("£18") == "£18"
    assert parse_price("£15.00") == "£15"
    assert parse_price("£12.5") == "£12.50"
    assert parse_price("Free") == "free"
    assert parse_price("free") == "free"
    assert parse_price("Free/donations") == "free"
    assert parse_price("£13 / 10 / 5") == "£13"
    assert parse_price("£20 Advance / 23 Door") == "£23"
    assert parse_price("£10 (8 students) + booking fee") == "£10"
    assert parse_price("£19.25, 26.25, Under 18’s Free") == "£26.25"
    assert parse_price("£9 - 22 advance") == "£9–22"
    assert parse_price("£12–15") == "£15"
    assert parse_price("£28.68 - 51.42") == "£51.42"  # < 2x: the high
    assert parse_price("£7.50 - 25") == "£7.50–25"
    assert parse_price("From 15") is None
    assert parse_price("") is None


def test_registered_whitelist_source_with_unique_slugs():
    registry = load_all()
    _scraper, source = registry[SOURCE_SLUG]
    assert all(v.city_slug == "london" for v in source.venues)
    assert set(ALIASES.values()) == {v.slug for v in VENUES}
    assert not set(ALIASES) & EXCLUDED
    owners: dict[str, str] = {}
    for slug, (_s, src) in registry.items():
        for v in src.venues:
            assert v.slug not in owners or owners[v.slug] == slug, v.slug
            owners[v.slug] = slug
