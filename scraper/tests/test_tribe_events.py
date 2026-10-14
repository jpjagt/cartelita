import datetime as dt
import json

from cartelera.scrapers import _tribe_events as tribe
from cartelera.scrapers._eur import eur_amounts, format_eur


def test_format_eur_house_convention():
    assert format_eur(15.5) == "15,50€"
    assert format_eur(9.0) == "9€"
    assert format_eur(7.95) == "7,95€"
    assert format_eur(0) == "free"


def test_eur_amounts_ignore_times_before_the_sign():
    assert eur_amounts("/ Early entry before 23:30 €15") == [15.0]
    assert eur_amounts("€ 15.5") == [15.5]
    assert eur_amounts("Aan de deur altijd €5,50") == [5.5]
    assert eur_amounts("12,50 €") == [12.5]


def test_cost_price_from_tribe_fields():
    assert tribe.cost_price({"cost": "Gratis", "cost_details": {"values": ["0"]}}) == "free"
    assert tribe.cost_price({"cost": "€ 12", "cost_details": {"values": ["12"]}}) == "12€"
    assert tribe.cost_price({"cost": "", "cost_details": {"values": []}}) is None
    assert tribe.cost_price({"cost": "Uitverkocht"}) == "sold-out"


def test_start_and_all_day():
    ev = {"start_date": "2026-10-21 20:00:00", "all_day": False}
    assert tribe.start(ev) == (dt.date(2026, 10, 21), dt.time(20, 0))
    ev = {"start_date": "2026-10-21 00:00:00", "all_day": True}
    assert tribe.start(ev) == (dt.date(2026, 10, 21), None)


def test_fetch_all_follows_next_rest_url(monkeypatch):
    pages = {
        tribe.events_url("https://x.nl"): {"events": [{"id": 1}], "next_rest_url": "https://x.nl/p2"},
        "https://x.nl/p2": {"events": [{"id": 2}]},
    }
    monkeypatch.setattr(tribe, "fetch", lambda url, headers=None: json.dumps(pages[url]))
    assert [e["id"] for e in tribe.fetch_all("https://x.nl")] == [1, 2]


def test_text_unescapes_html():
    assert tribe.text("dB&#8217;s &#038; TivoliVredenburg") == "dB’s & TivoliVredenburg"
