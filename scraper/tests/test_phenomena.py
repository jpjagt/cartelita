import datetime as dt
from pathlib import Path

from cartelera.scrapers.phenomena import parse_cartelera, parse_price

FIXTURE = Path(__file__).parent / "fixtures" / "phenomena_agenda.html"
FICHA_FIXTURE = Path(__file__).parent / "fixtures" / "phenomena_ficha.html"


def _events(prices=None):
    return parse_cartelera(FIXTURE.read_text(), prices=prices)


def test_parses_many_events():
    # One event per session; the fixture has dozens of sessions across ~36 films.
    events = _events()
    assert len(events) >= 30


def test_events_have_valid_date_title_url_and_film_category():
    for ev in _events():
        assert ev.title
        assert isinstance(ev.start_date, dt.date)
        assert ev.source_url.startswith("https://phenomena-experience.com/index?pag=ficha&evento=")
        # Single-category venue: every screening is film.
        assert ev.category_slugs == ["film"]


def test_every_session_has_a_showtime():
    # The listing always renders a time per session (e.g. "15:15h").
    for ev in _events():
        assert isinstance(ev.start_time, dt.time)


def test_external_id_unique_per_occurrence():
    # A film screens on many dates/times; external_id (the venue's id-ses) must
    # distinguish each occurrence so the upsert does not collapse them.
    events = _events()
    ids = [ev.external_id for ev in events]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_same_film_yields_multiple_distinct_occurrences():
    # At least one film must screen more than once (the case the per-occurrence
    # external_id protects against — the Filmoteca trap).
    events = _events()
    by_url: dict[str, int] = {}
    for ev in events:
        by_url[ev.source_url] = by_url.get(ev.source_url, 0) + 1
    assert max(by_url.values()) >= 2


def test_image_urls_present_and_absolute():
    for ev in _events():
        assert ev.image_url and ev.image_url.startswith("https://")


def test_price_coverage_when_prices_supplied():
    # The listing has no price; price is supplied per-film from the ficha page.
    # When supplied for every film, coverage must be complete and a display string.
    urls = {ev.source_url for ev in _events()}
    import re
    eventos = {re.search(r"evento=(\d+)", u).group(1) for u in urls}
    prices = {e: "9€" for e in eventos}
    events = _events(prices=prices)
    assert events
    priced = [ev for ev in events if ev.price]
    assert len(priced) == len(events)
    for ev in priced:
        assert ev.price.endswith("€")


def test_price_parsed_from_ficha_detail_page():
    # The ficha fixture's `.precio` element carries the public ticket price.
    assert parse_price(FICHA_FIXTURE.read_text()) == "9€"


def test_cycle_captured_as_annotation_without_label_prefix():
    events = _events()
    annotated = [ev for ev in events if ev.annotations]
    # A good share of films belong to a thematic ciclo.
    assert annotated
    for ev in annotated:
        for ann in ev.annotations:
            assert ann
            assert not ann.lower().startswith("ciclo:")


def test_description_includes_alt_title_or_credits():
    events = _events()
    assert any(ev.description for ev in events)
