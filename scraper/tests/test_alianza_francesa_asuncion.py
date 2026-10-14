import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers.alianza_francesa_asuncion import (
    SITE_URL,
    categorize,
    parse_event,
    parse_ical,
    recent_posts,
)

FIXTURES = Path(__file__).parent / "fixtures"
POSTS = json.loads((FIXTURES / "alianza_francesa_asuncion_posts.json").read_text())
BEFORE = dt.date(2026, 9, 1)  # the September batch is still upcoming


def _post(post_id: int) -> dict:
    return next(p for p in POSTS if p["id"] == post_id)


def _event(post_id: int, today: dt.date = BEFORE):
    ical = (FIXTURES / f"alianza_francesa_asuncion_{post_id}.ics").read_text()
    return parse_event(ical, _post(post_id), today)


def test_af_cine_screening_from_ical_in_local_time():
    ev = _event(8353)
    assert ev.title == "AF Cine – Les Félins"
    # DTSTART:20260929T220000Z = 19:00 in Asunción (UTC−3).
    assert ev.start_date == dt.date(2026, 9, 29)
    assert ev.start_time == dt.time(19, 0)
    assert ev.category_slugs == ["film"]
    assert ev.source_url == f"{SITE_URL}/events/af-cine-les-felins/"
    assert ev.external_id == "8353"
    assert ev.image_url and ev.image_url.endswith(".jpg")
    assert ev.description and "Sinopsis" in ev.description
    assert ev.price is None  # the site states no price
    assert ev.annotations == []


def test_paraguayan_film_cycle_is_film():
    ev = _event(8357)
    assert ev.category_slugs == ["film"]
    assert ev.start_date == dt.date(2026, 9, 30)


def test_non_programme_items_are_dropped():
    assert _event(8368) is None  # La Terrasse: DJ sets / música, no programme label
    assert _event(8371) is None  # lecture cycle: Charla
    assert _event(8180) is None  # Francophonie day: Feria de países


def test_past_occurrences_are_dropped():
    assert _event(8353, today=dt.date(2026, 10, 14)) is None


def test_categorize_rules():
    assert categorize(["arte", "Cine"]) == ["film"]
    assert categorize(["comedia", "música", "Teatro"]) == ["theater"]
    assert categorize(["arte", "Charla", "Cine"]) == []
    assert categorize(["Dj sets", "música"]) == []


def test_recent_posts_window():
    recent = recent_posts(POSTS, dt.date(2026, 10, 14))
    assert recent and len(recent) < len(POSTS)
    assert 8353 in {p["id"] for p in recent}


def test_ical_parser_unfolds_lines_and_reads_dates():
    body = (
        "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Une très longue\r\n  soirée\\, au théâtre\r\n"
        "DTSTART;VALUE=DATE:20261105\r\nCATEGORIES:Teatro\r\nURL:https://x/y/\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    (vev,) = parse_ical(body)
    assert vev["SUMMARY"] == "Une très longue soirée\\, au théâtre"
    ev = parse_event(body, {"id": 1, "link": "https://x/y/"}, BEFORE)
    assert ev.title == "Une très longue soirée, au théâtre"
    assert (ev.start_date, ev.start_time) == (dt.date(2026, 11, 5), None)
    assert ev.category_slugs == ["theater"]
