import datetime as dt
from pathlib import Path

from cartelera.scrapers.auditori import parse_agenda, normalize_price, _category_for

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA = FIXTURES / "auditori_agenda.html"


def _events():
    return parse_agenda(AGENDA.read_text())


def test_parses_many_events():
    # 174 events fan out to ~248 sessions/occurrences.
    events = _events()
    assert len(events) >= 200


def test_events_have_dates_titles_urls():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("https://www.auditori.cat/ca/esdeveniment/")
        assert ev.source_url.endswith("/")
        assert ev.category_slugs[0] in {"classical", "jazz"}


def test_every_event_has_a_category():
    assert all(len(ev.category_slugs) == 1 for ev in _events())
    assert all(ev.category_slugs[0] in {"classical", "jazz"} for ev in _events())


def test_default_category_is_classical():
    events = _events()
    classical = [e for e in events if e.category_slugs == ["classical"]]
    # The venue is classical-first: the large majority of occurrences.
    assert len(classical) >= len(events) * 0.6


def test_jazz_events_are_categorized_jazz():
    # "Jazz & pop" programme events must land in jazz, not the classical default.
    jazz = [e for e in _events() if e.category_slugs == ["jazz"]]
    assert jazz, "expected jazz-categorized occurrences from the fixture"


def test_category_discriminator():
    assert _category_for("Jazz &amp; pop") == "jazz"
    assert _category_for("Jazz & pop") == "jazz"
    assert _category_for("Jazz &amp; pop / Nova Música") == "jazz"
    assert _category_for("Simfònica") == "classical"
    assert _category_for("Nova Música") == "classical"
    assert _category_for("Cambra") == "classical"
    assert _category_for("Educatiu") == "classical"
    assert _category_for(None) == "classical"
    assert _category_for("") == "classical"


def test_price_coverage_is_high():
    # The Jamboree trap test: nearly every occurrence must carry a price.
    # The ~13% without one are genuinely not a fixed ticket price — "A
    # determinar" (TBD) or museum-admission activities ("Activitat inclosa en
    # l'entrada al Museu", "Entrada al Museu de la Música"), which we honestly
    # leave as None rather than inventing a price.
    events = _events()
    with_price = [e for e in events if e.price]
    assert len(with_price) >= len(events) * 0.85


def test_prices_are_concise_and_normalized():
    for ev in _events():
        if ev.price in (None, "free", "sold-out"):
            continue
        # A concise display string like "25€" or "12–16€".
        assert ev.price.endswith("€"), f"unexpected price form: {ev.price!r}"
        assert len(ev.price) <= 10, f"price too verbose: {ev.price!r}"


def test_normalize_price():
    assert normalize_price("15 €") == "15€"
    assert normalize_price("25€") == "25€"
    assert normalize_price("A partir de 25 €") == "25€"
    # Minor spread (high < 2× low) collapses to the highest price per the 2× rule.
    assert normalize_price("De 12 € a 16 €") == "16€"
    # Meaningful spread (high >= 2× low) keeps the range.
    assert normalize_price("De 27 € a 85 €") == "27–85€"
    assert normalize_price("75 € / escola") == "75€"
    assert normalize_price("A determinar") is None
    assert normalize_price("Entrada del Museu") is None
    assert normalize_price("Entrada gratuïta") == "free"
    assert normalize_price("Accés lliure sense reserva prèvia. Aforament limitat.") == "free"
    assert normalize_price(None) is None
    assert normalize_price("") is None
    assert normalize_price("15 €", sold_out=True) == "sold-out"


def test_free_events_use_free_keyword():
    free = [e for e in _events() if e.price == "free"]
    assert free, "expected free (accés lliure / gratuïta) occurrences"


def test_external_ids_unique_per_occurrence():
    # external_id is the per-occurrence dedup key — no two sessions may collide,
    # or the upsert would silently collapse occurrences.
    ids = [e.external_id for e in _events()]
    assert all(ids), "every occurrence needs an external_id"
    assert len(ids) == len(set(ids)), "external_ids collapsed occurrences"


def test_multi_session_event_yields_multiple_occurrences():
    # An event with many sessions (e.g. "Visita guiada al Museu", 22 sessions)
    # must produce one occurrence per session, each on a distinct date.
    events = _events()
    by_url: dict[str, list] = {}
    for e in events:
        by_url.setdefault(e.source_url, []).append(e)
    multi = [evs for evs in by_url.values() if len(evs) >= 5]
    assert multi, "expected at least one event fanned out into many occurrences"
    for evs in multi:
        dates = {e.start_date for e in evs}
        assert len(dates) >= 2, "multi-session occurrences should span dates"


def test_concert_times_parsed():
    # Non-exhibition occurrences should mostly carry a start time.
    events = _events()
    timed = [e for e in events if e.start_time is not None]
    assert len(timed) >= len(events) * 0.7


def test_exhibitions_have_end_date_and_no_time():
    # Exposicions are date ranges shown without a meaningful start time.
    ranged = [e for e in _events() if e.end_date is not None]
    assert ranged, "expected exhibition date ranges"
    for e in ranged:
        assert e.end_date > e.start_date
        assert e.start_time is None


def test_annotations_capture_labels_without_category_leak():
    events = _events()
    annotated = [e for e in events if e.annotations]
    assert annotated, "expected programme-label annotations"
    # The exact category slugs must never leak into annotations (the venue's
    # human label "Jazz & pop" is fine as an annotation; the slug "jazz" is not).
    for e in events:
        assert "classical" not in e.annotations
        assert "jazz" not in e.annotations


def test_start_times_are_valid():
    for e in _events():
        if e.start_time is not None:
            assert isinstance(e.start_time, dt.time)
