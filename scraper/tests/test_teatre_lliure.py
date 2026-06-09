"""Offline tests for the Teatre Lliure scraper.

All tests run against the saved fixture (tests/fixtures/teatre_lliure_agenda.html)
and do not make network requests.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from cartelera.scrapers.teatre_lliure import (
    _build_event,
    _item_set_value,
    parse_agenda,
    parse_period,
    parse_price,
)

FIXTURE = Path(__file__).parent / "fixtures" / "teatre_lliure_agenda.html"
KNOWN_CATEGORY_SLUGS = {"theater", "kids", "dance", "flamenco"}


@pytest.fixture(scope="module")
def fixture_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def shows(fixture_html: str) -> list[dict]:
    return parse_agenda(fixture_html)


# ---------------------------------------------------------------------------
# parse_period tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, exp_start, exp_end",
    [
        ("21/05 — 21/06/26", dt.date(2026, 5, 21), dt.date(2026, 6, 21)),
        ("10/06 — 11/06/26", dt.date(2026, 6, 10), dt.date(2026, 6, 11)),
        ("16/06/26", dt.date(2026, 6, 16), None),
        ("18/09 — 25/10/25", dt.date(2025, 9, 18), dt.date(2025, 10, 25)),
        ("18/10/25", dt.date(2025, 10, 18), None),
        ("05, 08, 09, 14, 15 i 16/11/25", dt.date(2025, 11, 5), dt.date(2025, 11, 16)),
        ("21 i 22/11/25", dt.date(2025, 11, 21), dt.date(2025, 11, 22)),
        ("22 i 29/11/2025", dt.date(2025, 11, 22), dt.date(2025, 11, 29)),
        ("03/12/25 — 04/01/26", dt.date(2025, 12, 3), dt.date(2026, 1, 4)),
        ("21/11 - 29/11/25", dt.date(2025, 11, 21), dt.date(2025, 11, 29)),
    ],
)
def test_parse_period(text: str, exp_start: dt.date | None, exp_end: dt.date | None) -> None:
    start, end = parse_period(text)
    assert start == exp_start
    assert end == exp_end


def test_parse_period_no_year_returns_none() -> None:
    """Date strings without any year should return (None, None)."""
    start, end = parse_period("01/07 - 31/07")
    assert start is None
    assert end is None

    start, end = parse_period("05/10")
    assert start is None
    assert end is None


# ---------------------------------------------------------------------------
# parse_price tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("De 14 a 32 €", "14–32€"),   # hi >= 2*lo → range
        ("De 7 a 12 €", "12€"),        # hi < 2*lo → single (highest)
        ("De 8 a 18 €", "8–18€"),      # hi >= 2*lo → range
        ("Gratuït", "free"),
        ("Entrada gratuïta", "free"),
        ("10 €", "10€"),
        (None, None),
        ("", None),
    ],
)
def test_parse_price(raw: str | None, expected: str | None) -> None:
    assert parse_price(raw) == expected


# ---------------------------------------------------------------------------
# parse_agenda (list page)
# ---------------------------------------------------------------------------


def test_parse_agenda_returns_many_shows(shows: list[dict]) -> None:
    assert len(shows) >= 10


def test_every_show_has_title_and_href(shows: list[dict]) -> None:
    for show in shows:
        assert show["title"], f"Missing title: {show}"
        assert show["href"].startswith("/ca/"), f"Bad href: {show}"


def test_every_show_has_slug(shows: list[dict]) -> None:
    for show in shows:
        assert show["slug"], f"Missing slug: {show}"


def test_every_show_has_period_text(shows: list[dict]) -> None:
    for show in shows:
        assert show["period_text"], f"Missing period_text: {show}"


def test_most_shows_have_parseable_dates(shows: list[dict]) -> None:
    """At least 85% of shows must have a parseable start date."""
    parseable = sum(
        1 for s in shows if parse_period(s["period_text"])[0] is not None
    )
    ratio = parseable / len(shows)
    assert ratio >= 0.85, f"Only {parseable}/{len(shows)} shows have parseable dates"


def test_slugs_are_unique(shows: list[dict]) -> None:
    slugs = [s["slug"] for s in shows]
    assert len(slugs) == len(set(slugs)), "Duplicate slugs found"


def test_most_shows_have_images(shows: list[dict]) -> None:
    with_img = sum(1 for s in shows if s["image_url"])
    assert with_img / len(shows) >= 0.8, f"Only {with_img}/{len(shows)} shows have images"


# ---------------------------------------------------------------------------
# Category discrimination
# ---------------------------------------------------------------------------


def _make_detail_soup(item_sets: dict[str, str]) -> BeautifulSoup:
    """Build a minimal detail-page soup from a dict of {label: text}."""
    blocks = "\n".join(
        f'<div class="item-set"><h3>{label}</h3><p>{text}</p></div>'
        for label, text in item_sets.items()
    )
    return BeautifulSoup(f"<html><body>{blocks}</body></html>", "html.parser")


def test_category_theater_by_default(shows: list[dict]) -> None:
    """An ordinary show with no kids signals should be categorised as theater."""
    adult_shows = [s for s in shows if "elpetit" not in s["slug"]]
    assert adult_shows, "No adult shows found"
    show = adult_shows[0]
    # Use a detail soup with no age recommendation
    detail_soup = _make_detail_soup({"Preu": "De 14 a 32 €", "Horari": "A les 19.00 h"})
    ev = _build_event(show, detail_soup)
    if ev is not None:
        assert ev.category_slugs == ["theater"]


def test_category_kids_for_elpetit_slug(shows: list[dict]) -> None:
    """Shows with 'elpetit' in the URL slug should be classified as kids."""
    kids_shows = [s for s in shows if "elpetit" in s["slug"]]
    assert kids_shows, "No elpetit shows found in fixture"
    detail_soup = _make_detail_soup({"Preu": "De 7 a 12 €", "Edat recomanada": "De 3 a 5 anys"})
    for show in kids_shows:
        ev = _build_event(show, detail_soup)
        if ev is not None:
            assert ev.category_slugs == ["kids"], f"{show['title']} should be kids"


def test_category_kids_for_age_recommendation(shows: list[dict]) -> None:
    """Detail page with child age recommendation triggers kids category."""
    adult_shows = [s for s in shows if "elpetit" not in s["slug"]]
    show = adult_shows[0]
    detail_soup = _make_detail_soup({"Preu": "De 7 a 12 €", "Edat recomanada": "De 4 a 8 anys"})
    ev = _build_event(show, detail_soup)
    if ev is not None:
        assert ev.category_slugs == ["kids"]


def test_category_dance_for_dansa_metropolitana_in_desc(shows: list[dict]) -> None:
    """Shows whose list-page desc contains 'Dansa Metropolitana' should be dance."""
    dance_shows = [s for s in shows if s.get("desc") and "Dansa Metropolitana" in s["desc"]]
    assert dance_shows, "No Dansa Metropolitana show found in fixture"
    detail_soup = _make_detail_soup({"Preu": "De 14 a 32 €"})
    for show in dance_shows:
        ev = _build_event(show, detail_soup)
        if ev is not None:
            assert ev.category_slugs == ["dance"], f"{show['title']} should be dance"


def test_category_dance_for_ball_item_set(shows: list[dict]) -> None:
    """Shows with a 'BALL' item-set on the detail page should be dance."""
    adult_shows = [s for s in shows if "elpetit" not in s["slug"]]
    show = next(s for s in adult_shows if parse_period(s["period_text"])[0] is not None)
    detail_soup = _make_detail_soup({"Preu": "De 14 a 32 €", "BALL": "Rocío Molina"})
    ev = _build_event(show, detail_soup)
    assert ev is not None
    assert ev.category_slugs == ["dance"]


def test_category_dance_for_coreografia_item_set(shows: list[dict]) -> None:
    """Shows with a 'COREOGRAFIA' item-set on the detail page should be dance."""
    adult_shows = [s for s in shows if "elpetit" not in s["slug"]]
    show = next(s for s in adult_shows if parse_period(s["period_text"])[0] is not None)
    detail_soup = _make_detail_soup({"Preu": "De 14 a 32 €", "COREOGRAFIA I DIRECCIÓ": "Rocío Molina"})
    ev = _build_event(show, detail_soup)
    assert ev is not None
    assert ev.category_slugs == ["dance"]


def test_all_categories_are_known(shows: list[dict]) -> None:
    """_build_event should never emit an unknown category slug."""
    detail_soup = _make_detail_soup({"Preu": "De 14 a 32 €"})
    all_known = {"theater", "kids", "dance", "flamenco"}
    for show in shows:
        ev = _build_event(show, detail_soup)
        if ev is not None:
            for slug in ev.category_slugs:
                assert slug in all_known, f"Unknown category {slug!r} for {show['title']}"


# ---------------------------------------------------------------------------
# Event structure from _build_event
# ---------------------------------------------------------------------------


def test_build_event_valid_fields(shows: list[dict]) -> None:
    """A show with a full date should produce a well-formed ScrapedEvent."""
    show = next(s for s in shows if parse_period(s["period_text"])[0] is not None)
    detail_soup = _make_detail_soup({
        "Preu": "De 14 a 32 €",
        "Horari": "De dimecres a dissabte a les 19.00 h",
    })
    ev = _build_event(show, detail_soup)
    assert ev is not None
    assert isinstance(ev.start_date, dt.date)
    assert ev.source_url.startswith("https://www.teatrelliure.com/ca/")
    assert ev.title
    assert ev.external_id == show["slug"]
    assert ev.price == "14–32€"
    assert ev.category_slugs


def test_build_event_price_free(shows: list[dict]) -> None:
    show = next(s for s in shows if parse_period(s["period_text"])[0] is not None)
    detail_soup = _make_detail_soup({"Preu": "Gratuït"})
    ev = _build_event(show, detail_soup)
    assert ev is not None
    assert ev.price == "free"


def test_build_event_room_in_annotations(shows: list[dict]) -> None:
    show = next(s for s in shows if s.get("room") and parse_period(s["period_text"])[0] is not None)
    detail_soup = _make_detail_soup({"Preu": "De 14 a 32 €"})
    ev = _build_event(show, detail_soup)
    assert ev is not None
    assert show["room"] in ev.annotations


def test_build_event_skips_dateless_shows(shows: list[dict]) -> None:
    """Shows whose date can't be parsed should return None from _build_event."""
    dateless = [s for s in shows if parse_period(s["period_text"])[0] is None]
    if not dateless:
        pytest.skip("No dateless shows in fixture")
    detail_soup = _make_detail_soup({})
    for show in dateless:
        ev = _build_event(show, detail_soup)
        assert ev is None, f"Expected None for dateless show {show['title']!r}"


# ---------------------------------------------------------------------------
# _item_set_value helper
# ---------------------------------------------------------------------------


def test_item_set_value_found() -> None:
    html = """
    <div class="item-set"><h3>Preu</h3><p>De 14 a 32 €</p></div>
    <div class="item-set"><h3>Horari</h3><p>A les 19.00 h</p></div>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert _item_set_value(soup, "Preu") == "De 14 a 32 €"
    assert _item_set_value(soup, "Horari") == "A les 19.00 h"


def test_item_set_value_missing_returns_none() -> None:
    html = '<div class="item-set"><h3>Preu</h3><p>De 14 a 32 €</p></div>'
    soup = BeautifulSoup(html, "html.parser")
    assert _item_set_value(soup, "Lloc") is None
