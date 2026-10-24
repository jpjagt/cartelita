import datetime as dt
import json
from pathlib import Path

import httpx

from cartelera.scrapers import _dice as dice
from cartelera.scrapers import dice_london

FIXTURES = Path(__file__).parent / "fixtures"
MOTH = dice.Venue("moth-club", "MOTH Club", "moth-club-43ox", {dice_london.GIG: "pop"},
                  genres=dice_london.GENRES, api_key="k")
UNION = dice.Venue("union-chapel", "Union Chapel", "union-chapel-jx9a", {dice_london.GIG: "pop"})


def _api_client():
    payload = json.loads((FIXTURES / "dice_moth_api.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "k"
        assert request.url.params["filter[venues][]"] == "MOTH Club"
        return httpx.Response(200, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_local_time_handles_utc_and_offsets():
    assert dice.local("2026-10-24T22:00:00Z", "Europe/London") == dt.datetime(2026, 10, 24, 23, 0)
    assert dice.local("2026-10-27T19:00:00Z", "Europe/London") == dt.datetime(2026, 10, 27, 19, 0)
    assert dice.local("2026-10-24T19:00:00+01:00") == dt.datetime(2026, 10, 24, 19, 0)


def test_price_from_pence():
    assert dice.price_from_pence([1360]) == "£13.60"
    assert dice.price_from_pence([1200, 1500]) == "£15"
    assert dice.price_from_pence([1000, 2500]) == "£10–25"
    assert dice.price_from_pence([0]) == "free"
    assert dice.price_from_pence([None]) is None


def test_event_url_shapes():
    assert dice.event_url({"id": "1", "hash": "av3oad", "perm_name": "x-tickets"}) == \
        "https://dice.fm/event/av3oad-x-tickets"
    assert dice.event_url({"id": "1", "perm_name": "2w5mmm-x-tickets"}) == "https://dice.fm/event/2w5mmm-x-tickets"
    assert dice.event_url({"id": "abc"}) == "https://dice.fm/event/abc"


def test_key_mode_keeps_gigs_and_refines_by_genre():
    with _api_client() as http:
        events = dice.to_scraped(MOTH, dice.api_events(MOTH, http))
    raw = json.loads((FIXTURES / "dice_moth_api.json").read_text())["data"]
    gigs = [e for e in raw if "music:gig" in e["type_tags"] and e["status"] != "cancelled"]
    assert len(events) == len(gigs)  # DJ nights dropped
    by_title = {e.title: e for e in events}
    knats = by_title["Knats"]
    assert knats.category_slugs == ["pop"] and knats.price == "sold-out"
    assert knats.source_url.startswith("https://dice.fm/event/") and knats.external_id
    # The event's first genre tag with a mapping decides (a folk-then-rock gig is folk).
    first = {e["id"]: next((dice_london.GENRES[g] for g in e["genre_tags"] if g in dice_london.GENRES), None)
             for e in gigs}
    rock_ids = {i for i, cat in first.items() if cat == "rock"}
    assert rock_ids
    assert {e.external_id for e in events if e.category_slugs == ["rock"]} == rock_ids


def test_categorize_drops_unmapped_types_and_cancelled():
    ev = dice.DiceEvent("1", "Stand-up", dt.datetime(2026, 11, 1, 20), ["culture:comedy"], [], "on-sale",
                        False, "£10", "u", None, None)
    assert dice.categorize(UNION, ev) == []
    gig = dice.DiceEvent("2", "Band", dt.datetime(2026, 11, 1, 20), ["music:gig"], [], "cancelled",
                         False, "£10", "u", None, None)
    assert dice.to_scraped(UNION, [gig]) == []


def test_public_mode_venue_page_and_event_pages(monkeypatch):
    venue_html = (FIXTURES / "dice_union_chapel_venue.html").read_text()
    details = json.loads((FIXTURES / "dice_union_chapel_events.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/venue/union-chapel-jx9a":
            return httpx.Response(200, text=venue_html)
        event_id = path.rsplit("/", 1)[-1]
        state = json.dumps({"event": {"event": details[event_id]}})
        page = {"props": {"pageProps": {"initialState": state}}}
        return httpx.Response(200, text=f'<script id="__NEXT_DATA__">{json.dumps(page)}</script>')

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        events = dice.to_scraped(UNION, dice.page_events(UNION, http))
    titles = " ".join(e.title for e in events)
    assert "Perfume Genius" in titles
    assert "Ghost House" not in titles  # culture:comedy
    assert all(e.category_slugs == ["pop"] and e.price for e in events)
    assert all(e.source_url.startswith("https://dice.fm/event/") and "-tickets" in e.source_url for e in events)
    assert all(e.description for e in events)


def test_every_london_dice_venue_is_registered_one_to_one():
    from cartelera.scrapers import REGISTRY, load_all
    load_all()
    dice_sources = {s: src for s, (sc, src) in REGISTRY.items() if isinstance(sc, dice_london.DiceVenueScraper)}
    assert len(dice_sources) == 22
    for slug, src in dice_sources.items():
        [venue] = src.venues
        assert venue.slug == slug and venue.city_slug == "london"
        cats = venue.category_slugs
        assert {m.list_slug for m in venue.list_memberships} == set(cats)
