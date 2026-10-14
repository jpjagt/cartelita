"""Tests for the Cineville multi-venue API source (Rotterdam + Utrecht arthouse
cinemas). Offline, against a saved (trimmed) API response."""
from __future__ import annotations
import datetime as dt
import json
from collections import Counter
from pathlib import Path

from cartelera.scrapers import load_all
from cartelera.scrapers.cineville import (
    SOURCE_SLUG,
    VENUE_IDS,
    _language,
    is_excluded,
    parse_events,
)

FIXTURES = Path(__file__).parent / "fixtures"
ITEMS = json.loads((FIXTURES / "cineville_events.json").read_text())
EVENTS = parse_events(ITEMS)
BY_ID = {e.external_id: e for e in EVENTS}


def _item(pred) -> dict:
    return next(i for i in ITEMS if pred(i))


def test_parses_every_whitelisted_venue():
    counts = Counter(e.venue_slug for e in EVENTS)
    assert set(counts) == set(VENUE_IDS)
    assert len(EVENTS) > 400


def test_registered_as_whitelist_source():
    _scraper, source = load_all()[SOURCE_SLUG]
    assert {v.slug for v in source.venues} == set(VENUE_IDS)
    assert {v.city_slug for v in source.venues} == {"rotterdam", "utrecht"}
    for v in source.venues:
        assert v.category_slugs == ["film"]


def test_ignores_venues_outside_whitelist():
    lantaren = dict(ITEMS[0], id="x", venueId="0d726ad9-55da-415b-8c92-e15902a29b08")
    assert parse_events([lantaren]) == []


def test_every_event_fully_populated():
    for e in EVENTS:
        assert e.title and e.title == e.title.strip()
        assert isinstance(e.start_date, dt.date)
        assert e.start_time is not None
        assert e.source_url.startswith("http")
        assert e.category_slugs == ["film"]
        assert e.price is None
        assert e.venue_slug in VENUE_IDS


def test_external_ids_unique_per_occurrence():
    ids = [e.external_id for e in EVENTS]
    assert len(ids) == len(set(ids))


def test_utc_converted_to_amsterdam_local():
    # 2026-10-21T19:00Z is 21:00 CEST; post-DST (25 Oct) it's UTC+1.
    item = _item(lambda i: i["startDate"] == "2026-10-21T19:00:00.000Z"
                 and i["venueId"] == VENUE_IDS["kino-rotterdam"])
    e = BY_ID[item["id"]]
    assert (e.start_date, e.start_time) == (dt.date(2026, 10, 21), dt.time(21, 0))
    winter = parse_events([dict(item, id="w", startDate="2026-11-18T20:00:00.000Z",
                                endDate="2026-11-18T23:30:00.000Z")])[0]
    assert winter.start_time == dt.time(21, 0)
    assert winter.end_time == dt.time(0, 30) and winter.end_date == dt.date(2026, 11, 19)


def test_hidden_events_dropped():
    hidden = [i for i in ITEMS if i["isHidden"]]
    assert hidden
    assert not any(i["id"] in BY_ID for i in hidden)


def test_excluded_series_dropped():
    assert is_excluded("louis-hartlooper", "De Ins en Outs van Film deel 4")
    assert is_excluded("slachtstraat", "Schrijfcafé")
    assert not is_excluded("louis-hartlooper", "Schrijfcafé")  # per venue
    assert not is_excluded("kino-rotterdam", "Event Horizon")
    titles = {e.title for e in EVENTS}
    assert "Schrijfcafé" not in titles
    assert not any(t.startswith("De Ins en Outs") for t in titles)


def test_language_is_subtitles_as_stated():
    assert _language(["en"]) == "EN subs"
    assert _language(["nl"]) == "NL subs"
    assert _language([]) is None and _language(None) is None
    langs = Counter(e.language for e in EVENTS)
    assert langs["NL subs"] > 100 and langs["EN subs"] > 5
    item = _item(lambda i: not (i["attributes"].get("subtitles")) and not i["isHidden"]
                 and i["id"] in BY_ID)
    assert BY_ID[item["id"]].language is None


def test_title_subs_suffix_lifted_into_language():
    item = _item(lambda i: (i["productionHint"] or {}).get("title", "").endswith("| Eng Subs"))
    e = BY_ID[item["id"]]
    assert "|" not in e.title and "Subs" not in e.title
    assert e.language == "EN subs"


def test_title_prefers_venue_pos_title():
    item = _item(lambda i: (i["productionHint"] or {}).get("title", "").startswith(
        "Children Who Chase Lost Voices (2011)"))
    assert BY_ID[item["id"]].title == "Children Who Chase Lost Voices (2011)"


def test_unlinked_events_kept_with_hint_title():
    unlinked = [i for i in ITEMS if not i["_embedded"] and i["id"] in BY_ID]
    assert unlinked
    for i in unlinked:
        assert BY_ID[i["id"]].title == i["productionHint"]["title"].strip()


def test_tags_become_annotations():
    tagged = [e for e in EVENTS if e.annotations]
    assert tagged
    assert {a for e in tagged for a in e.annotations} <= {"classic", "preview", "special", "70mm"}


def test_homepage_ticket_url_falls_back_to_cineville_film_page():
    cinerama = [i for i in ITEMS if i["venueId"] == VENUE_IDS["cinerama"]]
    assert cinerama
    for i in cinerama:
        url = BY_ID[i["id"]].source_url
        if i["_embedded"]:
            slug = i["_embedded"]["production"]["slug"]
            assert url == f"https://www.cineville.nl/films/{slug}"
        else:  # no film page to point at: keep the venue's own link
            assert url == i["ticketingUrl"]
    kino = [e for e in EVENTS if e.venue_slug == "kino-rotterdam"]
    assert all("kinorotterdam.nl/tickets/" in e.source_url for e in kino)


def test_image_and_description_coverage():
    linked = [e for e in EVENTS if e.description is not None]
    assert len(linked) > len(EVENTS) * 0.75
    assert sum(1 for e in EVENTS if e.image_url) > len(EVENTS) * 0.75
