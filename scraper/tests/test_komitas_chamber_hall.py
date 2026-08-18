"""Tests for the Komitas Chamber Music House scraper.

All tests run offline against saved HTML fixtures — no network access.
"""
from __future__ import annotations
import datetime as dt
from pathlib import Path

from cartelera.scrapers.komitas_chamber_hall import (
    format_price,
    merge_events,
    parse_place,
    parse_schedule,
)

FIXTURES = Path(__file__).parent / "fixtures"
PLACE_AM = (FIXTURES / "komitas_chamber_hall_place_am.html").read_text()
PLACE_EN = (FIXTURES / "komitas_chamber_hall_place_en.html").read_text()
TICKET_5713 = (FIXTURES / "komitas_chamber_hall_ticket_5713.html").read_text()
TICKET_5904 = (FIXTURES / "komitas_chamber_hall_ticket_5904.html").read_text()


# ---------------------------------------------------------------------------
# parse_place
# ---------------------------------------------------------------------------

def test_parse_place_am_finds_all_blocks():
    events = parse_place(PLACE_AM)
    assert len(events) == 9, f"expected 9 events, got {len(events)}"


def test_parse_place_en_finds_all_blocks():
    events = parse_place(PLACE_EN)
    assert len(events) == 9, f"expected 9 events, got {len(events)}"


def test_parse_place_events_have_required_fields():
    for ev in parse_place(PLACE_EN):
        assert ev.title, "missing title"
        assert ev.ticket_id, "missing ticket_id"
        assert ev.ticket_url.startswith("https://www.toms.am/"), f"bad url: {ev.ticket_url}"
        assert ev.date is not None, f"missing date for {ev.title!r}"


def test_parse_place_no_duplicate_ticket_ids():
    ids = [e.ticket_id for e in parse_place(PLACE_EN)]
    assert len(ids) == len(set(ids)), "duplicate ticket ids in listing"


def test_parse_place_price_coverage():
    events = parse_place(PLACE_EN)
    with_price = [e for e in events if e.price_raw]
    assert len(with_price) >= len(events) * 0.9, \
        f"price_raw coverage {len(with_price)}/{len(events)} < 90%"


def test_parse_place_description_excludes_order_link():
    events = parse_place(PLACE_EN)
    for ev in events:
        assert ev.description
        assert "ORDER TICKETS" not in ev.description


def test_parse_place_am_and_en_share_ticket_ids():
    am_ids = {e.ticket_id for e in parse_place(PLACE_AM)}
    en_ids = {e.ticket_id for e in parse_place(PLACE_EN)}
    assert am_ids == en_ids


def test_parse_place_gurdjieff_event_fields():
    events = {e.ticket_id: e for e in parse_place(PLACE_EN)}
    ev = events["5904"]
    assert ev.title == "Gurdjieff and Armenian Medieval Sacred and Ritual Music"
    assert ev.date == dt.date(2026, 9, 4)
    assert ev.price_raw and "3000" in ev.price_raw and "5000" in ev.price_raw
    assert ev.category_label == "Concert, Festival, Contest"
    assert ev.image_url and ev.image_url.endswith(".png")


def test_parse_place_kids_labeled_event():
    events = {e.ticket_id: e for e in parse_place(PLACE_EN)}
    ev = events["5713"]
    assert "Organ" in ev.title
    assert ev.category_label == "Play or Event for Kids and Teens"


# ---------------------------------------------------------------------------
# parse_schedule
# ---------------------------------------------------------------------------

def test_parse_schedule_5904_authoritative_time():
    # The description prose says "Time: 19:00." but the box-office schedule
    # select says 19:30 — the schedule select must win (see SOURCE.md).
    sessions = parse_schedule(TICKET_5904)
    assert sessions == [("13907", dt.date(2026, 9, 4), dt.time(19, 30))]


def test_parse_schedule_5713():
    sessions = parse_schedule(TICKET_5713)
    assert sessions == [("13919", dt.date(2026, 9, 15), dt.time(19, 0))]


def test_parse_schedule_missing_select_returns_empty():
    assert parse_schedule("<html><body>no select here</body></html>") == []


# ---------------------------------------------------------------------------
# format_price (dram, shared 2x-range helper, symbol convention)
# ---------------------------------------------------------------------------

def test_format_price_minor_spread_collapses_to_highest():
    assert format_price("Price 3000, 4000, 5000֏") == "5000֏"


def test_format_price_large_spread_becomes_range():
    assert format_price("Price 3000, 5000, 8000, 10000 ֏") == "3000–10000֏"


def test_format_price_boundary_2x_is_a_range():
    # 3000 -> 6000 is exactly 2x: rule is >=, so this is a range.
    assert format_price("Price 3000, 4000, 5000, 7000֏") == "3000–7000֏"


def test_format_price_task_example():
    assert format_price("Price 2000, 3000, 4000, 5000֏") == "2000–5000֏"


def test_format_price_hyphen_range_source_text():
    assert format_price("Price 3000 - 10000֏") == "3000–10000֏"


def test_format_price_armenian_text():
    assert format_price("Տոմսերի արժեքը` 4000, 5000, 7000 դրամ") == "7000֏"


def test_format_price_no_digits():
    assert format_price("Price TBD") is None


def test_format_price_none():
    assert format_price(None) is None


# ---------------------------------------------------------------------------
# merge_events
# ---------------------------------------------------------------------------

def _schedules():
    return {
        "5904": parse_schedule(TICKET_5904),
        "5713": parse_schedule(TICKET_5713),
    }


def test_merge_events_parses_many():
    events = merge_events(parse_place(PLACE_AM), parse_place(PLACE_EN), _schedules())
    assert len(events) == 9


def test_merge_events_required_fields():
    events = merge_events(parse_place(PLACE_AM), parse_place(PLACE_EN), _schedules())
    for ev in events:
        assert ev.title.strip()
        assert isinstance(ev.start_date, dt.date)
        assert ev.source_url.startswith("https://www.toms.am/")
        assert ev.category_slugs == ["classical"]
        assert ev.language is None


def test_merge_events_uses_schedule_time_over_description_text():
    events = {e.external_id: e for e in merge_events(
        parse_place(PLACE_AM), parse_place(PLACE_EN), _schedules()
    )}
    ev = events["komitas-schedule-13907"]
    assert ev.start_date == dt.date(2026, 9, 4)
    assert ev.start_time == dt.time(19, 30)
    assert ev.price == "5000֏"


def test_merge_events_fallback_when_no_schedule():
    events = merge_events(parse_place(PLACE_AM), parse_place(PLACE_EN), {})
    assert len(events) == 9
    for ev in events:
        assert ev.start_time is None
        assert ev.external_id and ev.external_id.startswith("komitas-ticket-")


def test_merge_events_external_ids_unique():
    events = merge_events(parse_place(PLACE_AM), parse_place(PLACE_EN), _schedules())
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))
    assert all(ids)


def test_merge_events_canonical_is_armenian():
    events = {e.external_id: e for e in merge_events(
        parse_place(PLACE_AM), parse_place(PLACE_EN), _schedules()
    )}
    ev = events["komitas-schedule-13907"]
    assert "Գյուրջիև" in ev.title  # Armenian canonical title
    assert ev.translations, "expected an en translation"
    en_tr = ev.translations[0]
    assert en_tr.lang == "en"
    assert en_tr.title == "Gurdjieff and Armenian Medieval Sacred and Ritual Music"
    assert en_tr.source_url and "/en/ticket/5904" in en_tr.source_url


def test_merge_events_annotations_carry_category_label_not_leaking_into_category():
    events = merge_events(parse_place(PLACE_AM), parse_place(PLACE_EN), _schedules())
    for ev in events:
        assert "classical" not in ev.annotations
        for ann in ev.annotations:
            assert ann, "empty annotation"


def test_merge_events_price_coverage():
    events = merge_events(parse_place(PLACE_AM), parse_place(PLACE_EN), _schedules())
    with_price = [e for e in events if e.price]
    assert len(with_price) >= len(events) * 0.9


def test_merge_events_multi_session_ticket_produces_multiple_events():
    hy = parse_place(PLACE_AM)
    en = parse_place(PLACE_EN)
    schedules = {
        "5904": [
            ("100", dt.date(2026, 9, 4), dt.time(19, 30)),
            ("101", dt.date(2026, 9, 5), dt.time(19, 30)),
        ]
    }
    events = merge_events(hy, en, schedules)
    matching = [e for e in events if e.external_id in ("komitas-schedule-100", "komitas-schedule-101")]
    assert len(matching) == 2
    assert {e.start_date for e in matching} == {dt.date(2026, 9, 4), dt.date(2026, 9, 5)}
