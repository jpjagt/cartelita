"""Offline tests for the Cafe OTO scraper (saved fixtures)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from cartelera.scrapers import load_all
from cartelera.scrapers.cafe_oto import (
    VENUE_SLUG,
    events_from_items,
    is_date_range,
    keep_item,
    parse_date_header,
    parse_list_page,
    parse_residency_page,
    parse_times,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _items() -> list[dict]:
    items = []
    for p in (1, 2, 3, 5):
        page_items, _ = parse_list_page((FIXTURES / f"cafe_oto_events_p{p}.html").read_text())
        items.extend(page_items)
    return items


def _events():
    residencies = {
        "/events/fred-frith-2026/": (FIXTURES / "cafe_oto_event_fred-frith-2026.html").read_text()
    }
    return events_from_items(_items(), residencies)


def test_list_pages_and_pagination():
    items, has_next = parse_list_page((FIXTURES / "cafe_oto_events_p1.html").read_text())
    assert len(items) == 12 and has_next
    items5, has_next5 = parse_list_page((FIXTURES / "cafe_oto_events_p5.html").read_text())
    assert items5 and not has_next5


def test_time_and_date_parsing():
    assert parse_times("7.30pm") == (dt.time(19, 30), None)
    assert parse_times("2–5pm") == (dt.time(14), dt.time(17))
    assert parse_times("5.30–7pm") == (dt.time(17, 30), dt.time(19))
    assert parse_times("11am–6pm") == (dt.time(11), dt.time(18))
    assert parse_times("11.30–1pm") == (dt.time(11, 30), dt.time(13))
    assert parse_times("9am") == (dt.time(9), None)
    assert parse_date_header("Saturday 24 October 2026, 7.30pm") == (
        dt.date(2026, 10, 24), dt.time(19, 30), None)
    assert is_date_range("1–2 November 2026")
    assert is_date_range("30 October – 1 November 2026")
    assert not is_date_range("Sunday 1 November 2026, 7.30pm")


def test_events_fields_and_prices():
    events = _events()
    assert len(events) >= 30
    assert all(e.category_slugs == ["alternative"] for e in events)
    assert all(e.source_url.startswith("https://www.cafeoto.co.uk/events/") for e in events)
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))
    assert sum(e.price is not None for e in events) / len(events) >= 0.9

    space = next(e for e in events if e.title.startswith("SPACE (Lisa Ullén"))
    assert space.start_date == dt.date(2026, 10, 26) and space.start_time == dt.time(19, 30)
    assert space.price == "£19"  # door price; advance/members tiers skipped
    assert space.image_url and space.image_url.startswith("https://media.cafeoto.co.uk/")

    door = next(e for e in events if e.title == "BBBBBBB + Guttersnipe")
    assert door.price == "£17"  # live-stream and members' prices ignored
    assert door.annotations == ["Show + live stream"]

    sold = next(e for e in events if e.title == "Wendy Eisenberg + Tara Clerkin Trio")
    assert sold.price == "sold-out"
    assert sold.annotations == ["Upset The Rhythm presents"]

    matinee = next(e for e in events if e.external_id == "evan-parker-matinee-residency-3")
    assert matinee.start_time == dt.time(14) and matinee.end_time == dt.time(17)


def test_residency_expands_to_nights():
    nights = parse_residency_page((FIXTURES / "cafe_oto_event_fred-frith-2026.html").read_text())
    assert [n["date_text"] for n in nights] == [
        "Sunday 1 November 2026, 7.30pm", "Monday 2 November 2026, 7.30pm"]
    frith = [e for e in _events() if "Fred Frith – Two-Night Residency" in e.annotations]
    assert [e.start_date for e in frith] == [dt.date(2026, 11, 1), dt.date(2026, 11, 2)]
    assert {e.external_id for e in frith} == {"fred-frith-2026-1", "fred-frith-2026-2"}
    assert all(e.price == "£22" for e in frith)
    # Residencies whose page wasn't fetched are skipped, never emitted as a
    # single date-range event.
    assert not any(e.external_id == "schlippenbach-globe-unity-orchestra" for e in _events())


def test_structural_drops():
    items = _items()
    offsite = next(i for i in items if i["prefix"].startswith("OFFSITE"))
    cancelled = next(i for i in items if "cancelled" in i["status"])
    private = next(i for i in items if i["href"] == "")
    assert not keep_item(offsite) and not keep_item(cancelled) and not keep_item(private)
    titles = {e.title for e in _events()}
    assert offsite["title"] not in titles
    assert cancelled["title"] not in titles


def test_registered():
    _scraper, source = load_all()[VENUE_SLUG]
    (venue,) = source.venues
    assert venue.city_slug == "london" and venue.category_slugs == ["alternative"]
