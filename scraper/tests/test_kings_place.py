"""Kings Place on the shared Spektrix helper joined to the kingsplace.co.uk
what's-on cards, against saved (trimmed) responses (captured 2026-10-25)."""

import json
from collections import Counter
from pathlib import Path

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import kings_place as kp

FIXTURES = Path(__file__).parent / "fixtures"


def _cards():
    return kp.parse_cards((FIXTURES / "kings_place_site_listing.html").read_text())


def _scraped():
    events = json.loads((FIXTURES / "kings_place_spektrix_events.json").read_text())
    instances = json.loads((FIXTURES / "kings_place_spektrix_instances.json").read_text())
    programme = kp.Programme(_cards())
    programme.prepare(events, instances)
    selected = spk.select(events, instances, programme.categorize)
    return spk.build(kp.CLIENT, selected, {}, title=programme.title, url=programme.url)


def test_cards_carry_spektrix_id_and_genre_path():
    cards = _cards()
    assert len(cards) == 203
    genres = Counter(c["genre"] for c in cards)
    assert genres["classical"] > 30 and genres["folk"] > 20 and genres["jazz"] > 20
    assert {"contemporary", "words", "family", "comedy"} <= set(genres)
    assert any(c["online"] for c in cards)


def test_genre_path_is_the_category():
    scraped = _scraped()
    cats = Counter(e.category_slugs[0] for e in scraped)
    assert set(cats) == {"classical", "folk", "jazz"}
    assert all(len(e.category_slugs) == 1 for e in scraped)
    for e in scraped:
        assert f"/whats-on/{e.category_slugs[0]}/" in e.source_url
    assert len({e.external_id for e in scraped}) == len(scraped)


def test_other_genres_and_unlisted_events_dropped():
    titles = {e.title for e in _scraped()}
    for dropped in ("Nine Lessons and Carols for Curious People",  # comedy
                    "Independent Podcast Awards 2026",  # words
                    "Soumik Datta",  # contemporary
                    "Dec Test Event 2", "Secure My Booking", "Rotunda Restaurant"):  # not listed
        assert dropped not in titles, dropped
    assert any(t.startswith("The Tallis Scholars") for t in titles)


def test_has_next_page():
    assert kp.has_next_page('<a href="https://www.kingsplace.co.uk/whats-on/page/3/">', 2)
    assert not kp.has_next_page('<a href="/whats-on/page/9/">', 9)


def test_title_from_the_website_card():
    rns = next(e for e in _scraped() if "Royal Northern Sinfonia" in e.title)
    assert rns.title.startswith("Vivaldi")  # box office: "Royal Northern Sinfonia"


def test_listing_client_passes_a_403_with_the_browser_cookie(monkeypatch):
    calls = []

    class Gate(Exception):
        response = type("R", (), {"status_code": 403})()

    def fetch(url, headers=None, impersonate=False):
        calls.append((url, impersonate, (headers or {}).get("Cookie")))
        if impersonate:
            raise Gate("403 Forbidden")
        return "ok"

    page = type("P", (), {"user_agent": "UA", "cookie_header": "__cf_bm=x"})()
    monkeypatch.setattr(kp, "fetch", fetch)
    monkeypatch.setattr(kp, "browser_page", lambda url, **kw: page)
    client = kp.ListingClient()
    assert client.get(kp.LISTING_URL) == "ok"
    assert client.get(f"{kp.LISTING_URL}page/2/") == "ok"
    # curl_cffi once, then plain HTTP with the browser's cookie throughout.
    assert calls == [(kp.LISTING_URL, True, None), (kp.LISTING_URL, False, "__cf_bm=x"),
                     (f"{kp.LISTING_URL}page/2/", False, "__cf_bm=x")]


def test_listing_client_other_errors_fail(monkeypatch):
    class NotFound(Exception):
        response = type("R", (), {"status_code": 404})()

    def fetch(url, headers=None, impersonate=False):
        raise NotFound("404")

    monkeypatch.setattr(kp, "fetch", fetch)
    monkeypatch.setattr(kp, "browser_page", lambda url, **kw: (_ for _ in ()).throw(AssertionError("no browser")))
    try:
        kp.ListingClient().get(kp.LISTING_URL)
    except NotFound:
        pass
    else:
        raise AssertionError("a 404 is not a bot check")
