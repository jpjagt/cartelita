import datetime as dt
from pathlib import Path

from cartelera.scrapers.santa_maria_del_pi import (
    VENUE_SLUG,
    parse_agenda,
    _normalize_price,
    _is_concert,
)

FIXTURE = Path(__file__).parent / "fixtures" / "santa_maria_del_pi_agenda.html"


def _events():
    return parse_agenda(FIXTURE.read_text())


def test_parses_at_least_one_concert():
    # The agenda is mostly liturgy; the fixture month holds a handful of concerts.
    events = _events()
    assert len(events) >= 1


def test_masses_are_excluded():
    # The raw fixture is dominated by "Missa" entries; none must survive the filter.
    events = _events()
    titles = [e.title.lower() for e in events]
    assert not any("missa" in t for t in titles), f"Mass leaked into output: {titles}"


def test_offsite_celebration_excluded():
    # The "Celebració 25 anys…" act is at a different parish (el Prat) — not a concert.
    events = _events()
    assert not any("celebració" in e.title.lower() for e in events)


def test_events_have_dates_titles_urls_and_category():
    events = _events()
    assert events
    for ev in events:
        assert isinstance(ev.start_date, dt.date), f"Missing date: {ev}"
        assert ev.title, f"Missing title: {ev}"
        assert ev.source_url.startswith("https://"), f"Bad URL: {ev}"
        assert ev.category_slugs == ["classical"], f"Wrong category: {ev}"


def test_concert_has_basilica_detail_url():
    events = _events()
    concert = next(
        (e for e in events if "gegants" in e.title.lower()), None
    )
    assert concert is not None, "Expected the Cobla Sant Jordi / Gegants concert"
    assert "basilicadelpi" in concert.source_url
    assert concert.start_date == dt.date(2026, 6, 2)
    assert concert.start_time == dt.time(20, 0)


def test_every_event_has_a_start_time():
    events = _events()
    assert all(e.start_time is not None for e in events)


def test_every_event_has_external_id():
    events = _events()
    assert all(e.external_id for e in events)


def test_external_ids_unique_per_occurrence():
    events = _events()
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids)), "Duplicate external_ids collapse occurrences"


def test_no_duplicate_source_urls_when_distinct_events():
    # Distinct concerts should not share a source_url (would signal a coarse fallback).
    events = _events()
    urls = [e.source_url for e in events if "basilicadelpi.cat/ca/" in e.source_url and "agenda" not in e.source_url]
    assert len(urls) == len(set(urls)), "Duplicate detail-page source_urls found"


def test_prices_are_strings_or_none():
    for ev in _events():
        assert ev.price is None or isinstance(ev.price, str)


# --- unit tests for the pure helpers (don't depend on volatile fixture data) ---


def test_is_concert_accepts_concerts_rejects_masses():
    assert _is_concert("Concert dels 425 anys dels Gegants del Pi", "")
    assert _is_concert("Recital d'orgue", "")
    assert _is_concert("Concert coral de Nadal", "")
    assert not _is_concert("Missa", "Lloc: Capella de la Sang")
    assert not _is_concert("Missa Dominical", "")
    # A concert word in a liturgy-titled act must not flip it to a concert.
    assert not _is_concert("Missa amb cant coral", "")


def test_normalize_price_free():
    assert _normalize_price("Entrada lliure a tots") == "free"
    assert _normalize_price("Activitat gratuïta") == "free"


def test_normalize_price_sold_out():
    assert _normalize_price("Entrades exhaurides") == "sold-out"


def test_normalize_price_amount_picks_highest():
    assert _normalize_price("Preu: 10€ / socis 8€") == "10€"
    assert _normalize_price("Entrada 12 €") == "12€"


def test_normalize_price_none_when_absent():
    assert _normalize_price("Lloc: Basílica de Santa Maria del Pi") is None
    assert _normalize_price("") is None
    assert _normalize_price(None) is None
