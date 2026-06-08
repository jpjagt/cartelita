import datetime as dt
from pathlib import Path

from cartelera.scrapers.palau_musica import parse_programming, _parse_price

FIXTURE = Path(__file__).parent / "fixtures" / "palau_musica_programming.json"

KNOWN_CATEGORIES = {"classical", "jazz", "flamenco"}


def _events():
    return parse_programming(FIXTURE.read_text())


def test_parses_many_events():
    # The programme JSON yields one event per upcoming occurrence (~390).
    assert len(_events()) >= 200


def test_events_have_valid_date_title_url_category():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title and ev.title.strip()
        assert ev.source_url.startswith("https://www.palaumusica.cat/")
        assert len(ev.category_slugs) == 1
        assert ev.category_slugs[0] in KNOWN_CATEGORIES


def test_default_category_is_classical_and_jazz_present():
    events = _events()
    cats = {ev.category_slugs[0] for ev in events}
    # Most events are classical; the Barcelona Jazz Festival contributes jazz and
    # the "De Cajón!" / flamenco galas (#flamenc) contribute flamenco.
    classical = [e for e in events if e.category_slugs[0] == "classical"]
    jazz = [e for e in events if e.category_slugs[0] == "jazz"]
    flamenco = [e for e in events if e.category_slugs[0] == "flamenco"]
    assert cats <= KNOWN_CATEGORIES
    assert len(classical) > len(jazz)
    assert jazz, "expected some jazz events (jazz festival)"
    assert flamenco, "expected some flamenco events (#flamenc galas)"


def test_jazz_events_are_jazz_programming():
    # Jazz events come from the jazz-festival hashtag; the festival cycle label
    # stays in annotations as context (the bare "jazz" slug is stripped to avoid
    # leaking the category into annotations).
    jazz = [e for e in _events() if e.category_slugs[0] == "jazz"]
    for ev in jazz:
        blob = " ".join(ev.annotations).lower()
        assert "jazz" in blob, f"jazz event has no jazz context: {ev.title!r}"
        assert "jazz" not in [a.lower() for a in ev.annotations]


def test_price_coverage():
    events = _events()
    with_price = [e for e in events if e.price]
    # Price lives in the programming JSON; coverage is near-total. The convention
    # test that would have caught the Jamboree price bug.
    assert len(with_price) >= len(events) * 0.9


def test_prices_are_concise_display_strings():
    for ev in _events():
        if not ev.price or ev.price in {"free", "sold-out"}:
            continue
        # A plain value or a short range like "18€" / "35–75€" — never the raw
        # verbose string with member tiers.
        assert ev.price.endswith("€"), f"unexpected price form: {ev.price!r}"
        assert "(" not in ev.price and "/" not in ev.price
        assert len(ev.price) <= 12, f"price too verbose: {ev.price!r}"


def test_free_events_use_free_keyword():
    # The gratis flag / "Gratuït"·"Accés lliure" phrasing normalizes to "free".
    free = [e for e in _events() if e.price == "free"]
    assert free, "expected at least one free event"


def test_external_id_unique_per_occurrence():
    events = _events()
    ids = [e.external_id for e in events]
    assert all(ids), "every event must have an external_id"
    assert len(set(ids)) == len(ids), "external_id must be unique per occurrence"
    # The id is production-qualified by date+time, so a production with multiple
    # sessions produces distinct ids.
    assert any("@" in i and "T" in i for i in ids)


def test_annotations_do_not_leak_category_slugs():
    # Genre/series labels live in annotations; the category slug itself
    # ("classical"/"jazz") must never appear there.
    for ev in _events():
        lowered = {a.lower() for a in ev.annotations}
        assert "classical" not in lowered
        assert ev.category_slugs[0] not in ev.annotations


def test_start_times_consistent():
    for ev in _events():
        if ev.start_time:
            assert ev.start_times == [ev.start_time]
        else:
            assert ev.start_times == []


def test_price_normalizer():
    # Meaningful spread (high >= 2× low) keeps the range.
    assert _parse_price("de 35 a 75 €", False) == "35–75€"
    # Minor spreads (high < 2× low) collapse to the highest price per the 2× rule.
    assert _parse_price("De 38 a 68 euros", False) == "68€"
    assert _parse_price("28 i 38 €", False) == "38€"
    assert _parse_price("15 €", False) == "15€"
    assert _parse_price("18", False) == "18€"
    assert _parse_price("20.0", False) == "20€"
    assert _parse_price("12 € (Abonats, socis: 10 €)", False) == "12€"
    assert _parse_price("20 € / preu especial: 16 €", False) == "20€"
    assert _parse_price("Concert per invitació", False) is None
    assert _parse_price(None, False) is None
    assert _parse_price("Gratuït, aforament limitat", False) == "free"
    assert _parse_price("Accés lliure (aforament limitat)", False) == "free"
    assert _parse_price("39 €", True) == "free"  # gratis flag wins
