import datetime as dt
from pathlib import Path

from cartelera.scrapers.sala_beckett import parse_agenda

FIXTURES = Path(__file__).parent / "fixtures"
ESPECTACLES = FIXTURES / "sala_beckett_agenda.html"
ACTIVITATS = FIXTURES / "sala_beckett_activitats.html"


def _espectacles():
    return parse_agenda(ESPECTACLES.read_text())


def _activitats():
    return parse_agenda(ACTIVITATS.read_text())


def _all():
    return _espectacles() + _activitats()


def test_parses_many_events():
    # The espectacles list alone holds the full shows programme.
    assert len(_espectacles()) >= 20
    assert len(_activitats()) >= 30


def test_events_have_dates_titles_urls():
    for ev in _all():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("https://www.salabeckett.cat/")
        assert ev.category_slugs[0] in {"theater", "jazz"}


def test_every_event_has_a_category():
    assert all(len(ev.category_slugs) >= 1 for ev in _all())


def test_theatre_venue_defaults_to_theater():
    # Sala Beckett is a theatre: every event in the fixtures is `theater`.
    assert all(ev.category_slugs == ["theater"] for ev in _all())


def test_most_events_have_a_price():
    events = _all()
    with_price = [e for e in events if e.price]
    assert len(with_price) >= len(events) * 0.85


def test_free_events_use_free_keyword():
    # "Activitat gratuïta" must normalize to "free".
    free = [e for e in _all() if e.price == "free"]
    assert free, "expected free events from the fixture"


def test_price_is_concise():
    # No event should carry the raw verbose price string; we extract max or normalize.
    priced = [e for e in _all() if e.price and e.price != "free"]
    for ev in priced:
        assert len(ev.price) <= 10, f"price too verbose: {ev.price!r}"
        assert "Personatges" not in ev.price
        assert "Promoció" not in ev.price


def test_price_max_extracted_correctly():
    from cartelera.scrapers.sala_beckett import _parse_price
    assert _parse_price("D'11 € a 22 € Pack Anatomia de Ricard: 28 €") == "28€"
    assert _parse_price("D'11 € a 22 €") == "22€"
    assert _parse_price("10 € | Personatges de la Beckett 8 €") == "10€"
    assert _parse_price("Activitat gratuïta") == "free"
    assert _parse_price("Preu: 10€ | Personatges de la Beckett 8€") == "10€"
    assert _parse_price(None) is None
    assert _parse_price("") is None


def test_date_ranges_set_end_date_after_start():
    ranged = [e for e in _all() if e.end_date is not None]
    assert ranged, "expected multi-day runs with an end date"
    assert all(e.end_date > e.start_date for e in ranged)


def test_single_day_events_have_no_end_date():
    singles = [e for e in _all() if e.end_date is None]
    assert singles, "expected single-day events"


def test_single_day_events_capture_start_time():
    # Single-day shows list one start time; we should parse it for most of them.
    singles = [e for e in _all() if e.end_date is None]
    with_time = [e for e in singles if e.start_time is not None]
    assert len(with_time) >= len(singles) * 0.6


def test_multi_day_runs_have_no_ambiguous_start_time():
    # A weekly schedule has no single start time -> we leave it None and stash
    # the schedule in annotations instead.
    for e in _all():
        if e.end_date is not None:
            assert e.start_time is None


def test_post_type_captured_as_annotation():
    annotated = [e for e in _all() if e.annotations]
    assert annotated, "expected format/sub-type annotations on events"
    # The category slug must never leak into annotations.
    assert all("theater" not in e.annotations for e in _all())


def test_external_id_and_image_present():
    events = _espectacles()
    assert all(e.external_id for e in events)
    assert [e for e in events if e.image_url]


def test_no_duplicate_source_urls_within_a_page():
    urls = [e.source_url for e in _espectacles()]
    assert len(urls) == len(set(urls))


def test_closed_and_private_activities_are_excluded():
    # Activities marked "tancada al públic" (closed to the public) or
    # "exclusiva per als Personatges de la Beckett" (members-only) aren't
    # public calendar events — they must be filtered out entirely, and the
    # phrase must not survive in any kept event's price/title/annotations.
    events = _all()
    blob = " ".join(
        " ".join([e.title, e.price or "", *e.annotations]).lower() for e in events
    )
    assert "tancada al públic" not in blob
    assert "exclusiva per als personatges" not in blob
