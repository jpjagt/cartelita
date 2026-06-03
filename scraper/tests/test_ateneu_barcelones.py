import datetime as dt
from pathlib import Path

from cartelera.scrapers.ateneu_barcelones import parse_agenda, parse_price

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA = FIXTURES / "ateneu_barcelones_agenda.html"
CONCERT = FIXTURES / "ateneu_barcelones_concert.html"


def _events():
    return parse_agenda(AGENDA.read_text())


def test_parses_at_least_one_concert():
    # The agenda is broad; the fixture has exactly one future music concert.
    events = _events()
    assert len(events) >= 1


def test_only_concerts_emitted_not_talks():
    # The fixture page has 36 activities (tertúlies, book launches, round tables,
    # one visita guiada, etc.) and only 1 of them is a concert. Emitting more than a
    # handful would mean talks are leaking in.
    events = _events()
    assert len(events) <= 3
    # The lone concert is the Quartet Vivancos recital — found by predicate, not index.
    titles = {e.title for e in events}
    assert any("Quartet Vivancos" in t for t in titles)
    # None of the dropped non-music activities should appear.
    assert not any("Seminari de Filosofia" in t for t in titles)
    assert not any("Carlota Gurt" in t for t in titles)


def test_every_event_is_classical_only():
    for ev in _events():
        assert ev.category_slugs == ["classical"]


def test_events_have_dates_titles_urls():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("https://ateneubcn.cat/activitats/")


def test_concert_fields():
    ev = next(e for e in _events() if "Quartet Vivancos" in e.title)
    assert ev.start_date == dt.date(2026, 6, 10)
    assert ev.start_time == dt.time(18, 30)
    assert ev.image_url and ev.image_url.startswith("http")
    # The section label "Música" is captured as an annotation, never a category.
    assert "Música" in ev.annotations
    assert "classical" in ev.category_slugs


def test_section_label_does_not_leak_into_category():
    for ev in _events():
        lowered = {c.lower() for c in ev.category_slugs}
        assert "música" not in lowered
        assert "concerts" not in lowered
        assert ev.category_slugs == ["classical"]


def test_external_id_present_and_encodes_occurrence():
    for ev in _events():
        assert ev.external_id
        assert "@" in ev.external_id
        assert "T" in ev.external_id.split("@", 1)[1]


def test_external_id_is_unique_per_occurrence():
    events = _events()
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))


def test_price_parsed_from_detail_page():
    # The concert detail page shows "Socis — Gratuït / No socis — 20€"; we take the
    # public (non-member) price and skip the member tier.
    price = parse_price(CONCERT.read_text())
    assert price == "20€"


def test_price_attached_when_supplied():
    # parse_agenda merges the per-URL prices fetched from detail pages.
    base = _events()
    ev = next(e for e in base if "Quartet Vivancos" in e.title)
    assert ev.price is None  # no prices passed in the offline list parse
    enriched = parse_agenda(
        AGENDA.read_text(), prices={ev.source_url: "20€"}
    )
    ev2 = next(e for e in enriched if "Quartet Vivancos" in e.title)
    assert ev2.price == "20€"


def test_price_normalization():
    free = '<p class="price nosocis">No socis — Gratuït</p>'
    sold = '<p class="price nosocis">Entrades exhaurides</p>'
    none = "<div>no price block here</div>"
    assert parse_price(free) == "free"
    assert parse_price(sold) == "sold-out"
    assert parse_price(none) is None
