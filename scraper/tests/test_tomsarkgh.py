"""Tests for the tomsarkgh.am multi-venue aggregator source.

All tests run offline against saved HTML fixtures — no network access.
"""
from __future__ import annotations
import datetime as dt
from pathlib import Path

from cartelera.scrapers import REGISTRY, load_all
from cartelera.scrapers.tomsarkgh import (
    SOURCE_SLUG,
    VENUE_IDS,
    categorize,
    format_amd,
    parse_price,
    build_event,
    parse_event_detail,
    parse_venue_listing_page,
)

FIXTURES = Path(__file__).parent / "fixtures"

KHACHATURIAN_VENUE = (FIXTURES / "tomsarkgh_khachaturian_venue.html").read_text()
KHACHATURIAN_MORE_P1 = (FIXTURES / "tomsarkgh_khachaturian_venue_more_p1.html").read_text()
OPERA_BALLET_VENUE = (FIXTURES / "tomsarkgh_opera_ballet_venue.html").read_text()
SUNDUKYAN_VENUE = (FIXTURES / "tomsarkgh_sundukyan_venue.html").read_text()
HAMAZGAYIN_VENUE = (FIXTURES / "tomsarkgh_hamazgayin_venue.html").read_text()
STANISLAVSKI_VENUE = (FIXTURES / "tomsarkgh_stanislavski_venue.html").read_text()

EVENT_JAZZ_POP = (FIXTURES / "tomsarkgh_event_51256_jazz_pop.html").read_text()
EVENT_CONCERT_POP = (FIXTURES / "tomsarkgh_event_51136_concert_pop.html").read_text()
EVENT_THEATER_FREE_CHILD = (FIXTURES / "tomsarkgh_event_43263_theater_free_child.html").read_text()


# ---------------------------------------------------------------------------
# parse_venue_listing_page — the site-wide "related events" carousel trap
# ---------------------------------------------------------------------------

def test_parse_venue_listing_filters_out_unrelated_carousel():
    # The venue page embeds a site-wide "related events" sidebar (other
    # venues' events — verified in recon to include e.g. a Coca-Cola-branded
    # concert, id 51211, which is definitely not a Sundukyan Theatre event)
    # alongside this venue's actual programme. Only cards carrying a
    # .event-venue link belong to the venue whose page we fetched.
    cards, _next = parse_venue_listing_page(SUNDUKYAN_VENUE)
    ids = {c["event_id"] for c in cards}
    assert "51211" not in ids  # the Coca-Cola Fest carousel card, not Sundukyan's
    # Sundukyan's own upcoming programme is much smaller than the raw
    # "all .event-box-item" count on the page (that also has the carousel).
    assert 1 <= len(cards) <= 10


def test_parse_venue_listing_page_returns_cards_with_type_and_url():
    cards, _next = parse_venue_listing_page(KHACHATURIAN_VENUE)
    assert len(cards) >= 8
    for c in cards:
        assert c["event_id"].isdigit()
        assert c["detail_url"].startswith("https://www.tomsarkgh.am/en/event/")
        assert c["type_label"]  # every real card has a type label


def test_parse_venue_listing_page_finds_more_pagination_link():
    _cards, next_url = parse_venue_listing_page(KHACHATURIAN_VENUE)
    assert next_url is not None
    assert "page/1" in next_url


def test_parse_venue_listing_more_fragment_also_filters_carousel():
    # The "more" pagination fragment repeats the same site-wide carousel
    # trap (no .event-list-wrapper container to lean on there), so the
    # .event-venue filter must work on fragments too, not just full pages.
    cards, _next = parse_venue_listing_page(KHACHATURIAN_MORE_P1)
    assert len(cards) >= 1
    for c in cards:
        assert c["event_id"].isdigit()


def test_parse_venue_listing_page_no_duplicate_event_ids():
    cards, _next = parse_venue_listing_page(OPERA_BALLET_VENUE)
    ids = [c["event_id"] for c in cards]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# parse_event_detail
# ---------------------------------------------------------------------------

def test_parse_event_detail_concert_event_fields():
    # A Sinatra/Wonder/Bublé pops-orchestra tribute night at Khachaturian
    # Hall — tomsarkgh's own type is "Concert" (its generic bucket), not
    # "Classical", so it maps to "pop" for this venue (see SOURCE.md).
    detail = parse_event_detail(EVENT_CONCERT_POP)
    assert detail is not None
    assert "Եռալեգենդ" in detail["title"]
    assert detail["start_date"] == dt.date(2026, 12, 13)
    assert detail["start_time"] == dt.time(20, 0)
    assert detail["type_label"] == "Concert"
    assert detail["price"] == "6000–12000 AMD"
    assert detail["description"]


def test_parse_event_detail_jazz_event_fields():
    detail = parse_event_detail(EVENT_JAZZ_POP)
    assert detail is not None
    assert detail["start_date"] == dt.date(2026, 8, 19)
    assert detail["start_time"] == dt.time(21, 0)
    assert detail["type_label"] == "Jazz"
    assert detail["price"] == "20000 AMD"
    assert detail["image_url"] and detail["image_url"].startswith("https://www.tomsarkgh.am/")


def test_parse_event_detail_theater_event_ignores_free_child_clause():
    # The description separately says "children under 4 enter free" — that's
    # a discount clause, not the general admission price, and must not turn
    # the price into "free".
    detail = parse_event_detail(EVENT_THEATER_FREE_CHILD)
    assert detail is not None
    assert detail["price"] == "1000–3000 AMD"
    assert detail["price"] != "free"


def test_parse_event_detail_missing_start_date_returns_none():
    assert parse_event_detail("<html><body><h1 id='eventName'>X</h1></body></html>") is None


# ---------------------------------------------------------------------------
# parse_price (AMD, hand-rolled — not the euro format_eur_range helper)
# ---------------------------------------------------------------------------

def test_parse_price_single_value():
    assert parse_price(["Տոմսերի արժեքը՝ 20000 ՀՀ դրամ։"]) == "20000 AMD"


def test_parse_price_large_spread_becomes_range():
    assert parse_price(["Տոմսերի արժեքը՝ 1000-5000 դրամ:"]) == "1000–5000 AMD"


def test_parse_price_minor_spread_collapses_to_highest():
    # 25000 -> 30000 is < 2x: not a meaningful spread, so the highest tier wins.
    assert parse_price(["Տոմսերի արժեքը՝ 25000, 30000 դրամ"]) == "30000 AMD"


def test_parse_price_comma_separated_list_not_merged_into_one_giant_number():
    # Regression: a naive digit-run regex reads "25000, 30000" as thousands
    # grouping and merges it into "2500030000". The two numbers must stay
    # distinct tokens.
    assert parse_price(["Տոմսերի արժեքը՝ 25000, 30000 դրամ"]) != "2500030000 AMD"


def test_parse_price_period_thousands_separator():
    assert parse_price(["Տոմսերի արժեքը ՝ 25.000 ՀՀ դրամ։"]) == "25000 AMD"


def test_parse_price_space_thousands_separator_in_range():
    assert parse_price(["Տոմսերի արժեքը՝ 3000-10 000 դրամ։"]) == "3000–10000 AMD"


def test_parse_price_russian_trigger_word():
    assert parse_price(["Цена билета: 8000 др"]) == "8000 AMD"


def test_parse_price_russian_range():
    assert parse_price(["Цена билета: 2000-5000 др"]) == "2000–5000 AMD"


def test_parse_price_trigger_line_with_no_digits_is_unknown():
    assert parse_price(["Билеты уже в продаже. Не пропустите эту битву."]) is None


def test_parse_price_no_trigger_line_is_unknown():
    assert parse_price(["Some unrelated line.", "Duration: 90 minutes."]) is None


def test_parse_price_ignores_free_child_clause_on_a_different_line():
    lines = ["Տոմսերի արժեքը՝ 1000-3000 դր.:", "Մինչև 4 տարեկան երեխայի մուտքն անվճար է:"]
    assert parse_price(lines) == "1000–3000 AMD"


def test_format_amd_boundary_2x_is_a_range():
    assert format_amd(3000, 6000) == "3000–6000 AMD"


def test_format_amd_equal_bounds():
    assert format_amd(5000, 5000) == "5000 AMD"


# ---------------------------------------------------------------------------
# categorize — the editorial per-venue mapping rules
# ---------------------------------------------------------------------------

def test_categorize_khachaturian_classical():
    assert categorize("khachaturian-hall", "Classical") == ["classical"]


def test_categorize_khachaturian_everything_else_is_pop():
    for label in ("Jazz", "Pop", "Concert", "Rock", "Folk", "Stand-up"):
        assert categorize("khachaturian-hall", label) == ["pop"], label


def test_categorize_opera_ballet_theatre_mappings():
    assert categorize("opera-ballet-theatre", "Opera") == ["classical"]
    assert categorize("opera-ballet-theatre", "Ballet") == ["dance"]
    assert categorize("opera-ballet-theatre", "Classical") == ["classical"]
    assert categorize("opera-ballet-theatre", "Dance") == ["dance"]
    assert sorted(categorize("opera-ballet-theatre", "Opera & Ballet")) == ["classical", "dance"]


def test_categorize_opera_ballet_theatre_skips_unrelated_bookings():
    for label in ("Jazz", "Pop", "Concert", "Stand-up"):
        assert categorize("opera-ballet-theatre", label) is None, label


def test_categorize_theater_venues_map_all_stage_genres_to_theater():
    for venue in ("sundukyan-theatre", "hamazgayin-theatre", "stanislavski-theatre"):
        for label in ("Theater", "Drama", "Tale", "Tragicomedy", "Comedy", "For kids"):
            assert categorize(venue, label) == ["theater"], (venue, label)


def test_categorize_theater_venues_skip_concert_and_standup_bookings():
    for venue in ("sundukyan-theatre", "hamazgayin-theatre", "stanislavski-theatre"):
        assert categorize(venue, "Concert") is None
        assert categorize(venue, "Stand-up") is None


def test_categorize_unknown_venue_returns_none():
    assert categorize("not-a-real-venue", "Theater") is None


# ---------------------------------------------------------------------------
# build_event — combining a listing card with its detail page
# ---------------------------------------------------------------------------

def _card(event_id: str, type_label: str, url: str = "https://www.tomsarkgh.am/en/event/1/x.html") -> dict:
    return {"event_id": event_id, "detail_url": url, "type_label": type_label}


def test_build_event_emits_venue_slug_and_seeded_categories():
    detail = parse_event_detail(EVENT_CONCERT_POP)
    ev = build_event("khachaturian-hall", _card("51136", "Concert"), detail)
    assert ev is not None
    assert ev.venue_slug == "khachaturian-hall"
    assert ev.category_slugs == ["pop"]
    assert ev.external_id == "tomsarkgh-51136"


def test_build_event_detail_type_label_takes_priority_over_card():
    # build_event prefers the detail page's own type_label when present (the
    # more authoritative per-event source, same principle as the skill's
    # "prefer the detail page" guidance) — a stale/wrong card-level label
    # must not override it.
    detail = parse_event_detail(EVENT_CONCERT_POP)
    ev = build_event("khachaturian-hall", _card("51136", "Classical"), detail)
    assert ev is not None
    assert ev.category_slugs == ["pop"]  # detail says "Concert", not "Classical"


def test_build_event_skips_unmapped_category():
    detail = parse_event_detail(EVENT_JAZZ_POP)
    # Pretend this jazz event happened at the opera-ballet theatre, which has
    # no fallback category for jazz bookings (unlike khachaturian-hall).
    ev = build_event("opera-ballet-theatre", _card("51256", "Jazz"), detail)
    assert ev is None


def test_build_event_sets_language_per_venue():
    detail = parse_event_detail(EVENT_THEATER_FREE_CHILD)
    ev = build_event("sundukyan-theatre", _card("43263", "Theater"), detail)
    assert ev is not None
    assert ev.language == "hy"


def test_build_event_khachaturian_pop_event_language_unset():
    detail = parse_event_detail(EVENT_JAZZ_POP)
    ev = build_event("khachaturian-hall", _card("51256", "Jazz"), detail)
    assert ev is not None
    assert ev.category_slugs == ["pop"]
    assert ev.language is None


def test_build_event_annotations_carry_site_type_label():
    detail = parse_event_detail(EVENT_CONCERT_POP)
    ev = build_event("khachaturian-hall", _card("51136", "Concert"), detail)
    assert ev.annotations == ["Concert"]


# ---------------------------------------------------------------------------
# Registration / whitelist invariants
# ---------------------------------------------------------------------------

def test_registered_as_multi_venue_source_with_five_venues():
    load_all()
    scraper, source = REGISTRY[SOURCE_SLUG]
    assert source.slug == SOURCE_SLUG
    assert {v.slug for v in source.venues} == set(VENUE_IDS)
    assert len(source.venues) == 5


def test_all_whitelisted_venues_are_yerevan():
    load_all()
    _scraper, source = REGISTRY[SOURCE_SLUG]
    assert all(v.city_slug == "yerevan" for v in source.venues)


def test_theater_venues_have_theater_list_membership():
    load_all()
    _scraper, source = REGISTRY[SOURCE_SLUG]
    by_slug = {v.slug: v for v in source.venues}
    for slug in ("sundukyan-theatre", "hamazgayin-theatre", "stanislavski-theatre"):
        memberships = by_slug[slug].list_memberships
        assert any(m.list_slug == "theater" for m in memberships)


def test_opera_ballet_theatre_is_in_both_classical_and_dance_lists():
    load_all()
    _scraper, source = REGISTRY[SOURCE_SLUG]
    by_slug = {v.slug: v for v in source.venues}
    slugs = {m.list_slug for m in by_slug["opera-ballet-theatre"].list_memberships}
    assert slugs == {"classical", "dance"}


def test_built_events_venue_slug_always_in_source_whitelist():
    # The invariant the runner enforces (_group_events_by_venue in run.py):
    # every emitted event's venue_slug must be one of the source's venues.
    load_all()
    _scraper, source = REGISTRY[SOURCE_SLUG]
    known = {v.slug for v in source.venues}
    fixtures_by_venue = {
        "khachaturian-hall": (KHACHATURIAN_VENUE,),
        "opera-ballet-theatre": (OPERA_BALLET_VENUE,),
        "sundukyan-theatre": (SUNDUKYAN_VENUE,),
        "hamazgayin-theatre": (HAMAZGAYIN_VENUE,),
        "stanislavski-theatre": (STANISLAVSKI_VENUE,),
    }
    detail_by_event_id = {
        "51136": EVENT_CONCERT_POP,
        "51256": EVENT_JAZZ_POP,
        "43263": EVENT_THEATER_FREE_CHILD,
    }
    built = []
    for venue_slug, pages in fixtures_by_venue.items():
        for page in pages:
            cards, _next = parse_venue_listing_page(page)
            for card in cards:
                html = detail_by_event_id.get(card["event_id"])
                if html is None:
                    continue
                detail = parse_event_detail(html)
                if detail is None:
                    continue
                ev = build_event(venue_slug, card, detail)
                if ev is not None:
                    built.append(ev)
    assert built, "expected at least one built event from the fixtures with matching details"
    assert all(ev.venue_slug in known for ev in built)


# --- network-failure behavior: fail loudly, never [ok] 0 events ---


def test_listing_fetch_failure_raises_instead_of_returning_empty():
    """An unreachable site must FAIL the source (keeping existing DB rows),
    not scrape as ok-with-zero-events — 0 events would silently mask outages
    and is indistinguishable from every venue being dormant."""
    import asyncio
    import httpx
    import pytest
    from cartelera.scrapers import tomsarkgh as t

    class _FailingClient:
        async def get(self, url, **kwargs):
            raise httpx.ConnectError("unreachable")

    async def run():
        sem = asyncio.Semaphore(1)
        return await t._scrape_venue(_FailingClient(), sem, "sundukyan-theatre")

    with pytest.raises(RuntimeError, match="listing fetch failed"):
        asyncio.run(run())
