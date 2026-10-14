import datetime as dt
from pathlib import Path

from cartelera.scrapers import laurenskerk as L

FIX = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 14)


def _detail(name):
    return L.parse_detail((FIX / f"laurenskerk_detail_{name}.html").read_text(), TODAY)


def test_agenda_cards_and_pagination():
    cards, nxt = L.parse_agenda((FIX / "laurenskerk_agenda.html").read_text())
    assert len(cards) >= 10
    assert nxt == "https://laurenskerk.nl/agenda/?pagination=2"
    for c in cards:
        assert c["url"].startswith("https://laurenskerk.nl/evenement/") and c["title"]
    assert sum(1 for c in cards if c["image_url"]) >= len(cards) - 1


def test_organ_concert_kept_with_time_and_price():
    d = _detail("organ")
    assert d["dates"] == [dt.date(2026, 10, 20)]
    assert d["start_times"] == [dt.time(20, 0)] and d["end_time"] == dt.time(21, 15)
    assert d["price"] == "9,50€"  # Regulier; Vrienden / t/m 26 tiers skipped
    assert L.keep(d)
    card = {"url": "https://laurenskerk.nl/evenement/orgel-grootmeesters-klee-droomt-bach-met-hayo-boerema/",
            "title": "Orgel Grootmeesters Klee droomt Bach met Hayo Boerema", "tagline": None, "image_url": None}
    (ev,) = L.build_events(card, d)
    assert ev.category_slugs == ["classical"]
    assert ev.external_id == "orgel-grootmeesters-klee-droomt-bach-met-hayo-boerema@2026-10-20T2000"
    assert ev.annotations == ["Orgelconcerten"]


def test_church_service_excluded():
    d = _detail("service")
    assert d["is_service"] and not L.keep(d)


def test_hired_franchise_excluded_by_ticket_platform():
    d = _detail("candlelight")
    assert d["categories"] == ["Concerten"] and "feverup.com" in d["ticket_url"]
    assert not L.keep(d)


def test_touring_classical_kept_with_regular_price():
    d = _detail("touring")
    assert L.keep(d)
    assert d["price"] == "90€"  # "Met vroegboekkorting €54,95 ipv € 90,-"


def test_two_shows_and_non_music_category():
    d = _detail("twoshows")
    assert d["start_times"] == [dt.time(19, 30), dt.time(21, 15)]
    assert L.keep(d)  # Ademruimte + Orgelconcerten
    assert not L.keep(_detail("yoga"))  # Ademruimte only


def test_dates_parsing():
    assert L.parse_dates("vrijdag 13 november2026", TODAY) == [dt.date(2026, 11, 13)]
    assert L.parse_dates("woensdag 14 october 2026", TODAY) == [dt.date(2026, 10, 14)]
    assert L.parse_dates("woensdag 21 oktober donderdag 22 oktober", TODAY) == [
        dt.date(2026, 10, 21), dt.date(2026, 10, 22)]


def test_price_rules():
    assert L.parse_price(["€39,-", "geplaceerd €69,-"]) == "69€"
    assert L.parse_price(["Toegang is vrij, collecte na afloop Adoptiestoel €60,-"]) == "free"
    assert L.parse_price(["Pay what you can"]) == "pay what you can"
    assert L.parse_price(["Met vroegboekkorting €54,95"]) is None
    assert L.parse_price(["Normaal €40,-", "tot 30 jaar €19,-"]) == "40€"
