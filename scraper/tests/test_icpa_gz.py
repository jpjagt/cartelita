import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers.icpa_gz import at_own_venue, categorize, parse_events, price

RAW = json.loads((Path(__file__).parent / "fixtures" / "icpa_gz_events.json").read_text())


def _events():
    return parse_events(RAW)


def _by_title(fragment: str):
    return next(e for e in _events() if fragment in e.title)


def test_keeps_programme_and_drops_the_rest():
    events = _events()
    # 369 calendar items (Oct 2026 upcoming + 2025-26 history): mostly
    # workshops, talks, courses, reading clubs and off-site partner events.
    assert 25 <= len(events) <= 40
    titles = " ".join(e.title for e in events)
    assert "Taller de Cerámica" not in titles  # Taller
    assert "Club de Lectura" not in titles  # no programme label
    assert "Noche Alemana" not in titles  # off-site (Colegio Goethe)
    assert "Cine Villamorra" not in " ".join(e.source_url for e in events)


def test_upcoming_concert_fields():
    ev = _by_title("Guitarra Paraguaya")
    assert ev.start_date == dt.date(2026, 10, 23)
    assert ev.start_time == dt.time(20, 0)
    assert ev.category_slugs == ["classical"]
    assert ev.price == "40.000₲"
    assert ev.source_url == "https://www.icpa-gz.org.py/evento/concierto-guitarra-paraguaya/"
    assert ev.image_url and ev.image_url.endswith(".jpeg")
    assert ev.annotations == ["Música"]


def test_film_cycles_and_kids():
    assert _by_title("Under de volcano").category_slugs == ["film"]
    assert _by_title("Checker Tobi").category_slugs == ["film", "kids"]


def test_every_event_is_categorized_and_priced():
    events = _events()
    assert all(e.category_slugs for e in events)
    assert all(e.price for e in events)  # cost field is always set
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))


def test_categorize_rules():
    assert categorize(["Arte", "Cine"]) == ["film"]
    assert categorize(["Cine", "Taller"]) == []
    assert categorize(["Danza", "Exposición"]) == []
    assert categorize(["Música"]) == []  # a listening party / DJ night isn't a concert
    assert categorize(["Concierto", "Música"]) == ["classical"]
    assert categorize(["Cine", "Evento para niñas y niños"]) == ["film", "kids"]


def test_price_in_guaranies():
    assert price({"cost": "Gs300.000", "cost_details": {"values": ["300.000"]}}) == "300.000₲"
    assert price({"cost": "Gs380000", "cost_details": {"values": ["380000"]}}) == "380.000₲"
    assert price({"cost": "Gratuito", "cost_details": {"values": ["0"]}}) == "free"
    assert price({"cost": "Gratuito", "cost_details": {"values": []}}) == "free"
    assert price({"cost": "", "cost_details": {"values": []}}) is None


def test_own_venue_rooms():
    assert at_own_venue({"venue": {"venue": "Salón Rolando Rasmussen del Instituto Cultural Paraguayo-Alemán – Goethe-Zentrum | ICPA-GZ"}})
    assert at_own_venue({"venue": {"venue": "Biblioteca Ulrich Schmidl del Instituto Cultural Paraguayo-Alemán &#8211; Goethe-Zentrum"}})
    assert not at_own_venue({"venue": {"venue": "Cine Villamorra"}})
    assert not at_own_venue({"venue": []})
