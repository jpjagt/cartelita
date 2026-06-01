import datetime as dt
from pathlib import Path
from cartelera.scrapers.harlem_jazz_club import parse_agenda

FIXTURE = Path(__file__).parent / "fixtures" / "harlem_jazz_club_agenda.html"


def _events():
    return parse_agenda(FIXTURE.read_text())


def test_parses_many_events():
    events = _events()
    assert len(events) >= 30  # /conciertos/ ships the whole upcoming agenda


def test_events_have_dates_titles_urls():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.title
        assert ev.source_url.startswith("https://www.harlemjazzclub.es/")
        # Single-category jazz venue.
        assert ev.category_slugs == ["jazz"]


def test_source_urls_are_unique():
    events = _events()
    urls = [e.source_url for e in events]
    assert len(urls) == len(set(urls))  # the duplicate-month cards must be deduped


def test_titles_are_clean():
    # The "HH:MMh | ", the genre parens and the trailing price must be stripped out
    # of the title.
    for ev in _events():
        assert "|" not in ev.title
        assert "€" not in ev.title
        assert not ev.title.lower().endswith(")")
        assert "  " not in ev.title


def test_most_events_have_a_price():
    events = _events()
    with_price = [e for e in events if e.price]
    assert len(with_price) >= len(events) * 0.9  # price is in nearly every title


def test_free_entry_recognized():
    events = _events()
    free = [e for e in events if e.price == "free"]
    assert free, "expected at least one free-entry ('free') event"


def test_numeric_prices_are_euro_freetext():
    # Prices are free text, never parsed to numbers; numeric ones keep the € sign.
    for ev in _events():
        if ev.price and ev.price != "free":
            assert ev.price.endswith("€")
            assert ev.price[:-1].isdigit()


def test_most_events_have_a_showtime():
    events = _events()
    with_time = [e for e in events if e.start_time is not None]
    assert len(with_time) >= len(events) * 0.9  # title carries the "HH:MMh" showtime


def test_showtime_comes_from_title_not_bar_opening():
    # The card's data-time is the (earlier) bar-opening time; the showtime in the
    # title prefix is what we keep. For the Blues & Early Jazz Jam the title says
    # 22:30h while data-time encodes 20:30 — we must surface 22:30.
    events = _events()
    jam = next(e for e in events if "BLUES & EARLY JAZZ JAM" in e.title.upper())
    assert jam.start_time == dt.time(22, 30)


def test_genre_annotations_captured():
    events = _events()
    annotated = [e for e in events if e.annotations]
    assert len(annotated) >= len(events) * 0.9
    # Genres are split into individual tags, and the showtime/price never leak in.
    swing = next(e for e in events if e.title.upper().startswith("SWING TIME"))
    assert "flamenco" in swing.annotations
    assert "gipsy jazz" in swing.annotations
    for ev in events:
        for a in ev.annotations:
            assert "€" not in a
            assert "h |" not in a


def test_external_id_and_image_present():
    for ev in _events():
        assert ev.external_id  # EventON data-event_id
        assert ev.image_url and ev.image_url.startswith("http")


def test_closed_notice_has_no_time_or_price():
    # "CERRADO POR LA NOCHE DE SAN JUAN" is a venue-closed listing: no showtime
    # prefix, no genre, no price.
    events = _events()
    closed = [e for e in events if "CERRADO" in e.title.upper()]
    assert closed, "expected the San Juan closed notice in the fixture"
    c = closed[0]
    assert c.start_time is None
    assert c.price is None
    assert c.annotations == []


def test_free_entry_events_use_free_keyword():
    events = parse_agenda(FIXTURE.read_text())
    raw_html = FIXTURE.read_text()
    has_libre = "libre" in raw_html.lower() or "gratu" in raw_html.lower()
    if has_libre:
        assert any(e.price == "free" for e in events), "expected at least one 'free' priced event"
    # No event should have raw "Entrada libre" or "entrada libre" as price.
    assert not any(
        e.price and "libre" in e.price.lower() for e in events
    ), "raw 'entrada libre' string must be normalized to 'free'"
