import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers.maassilo import build_events, parse_agenda, parse_detail

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 14)
PREFIX = "maassilo_detail_"


def _details():
    return {
        f"https://maassilo.com/agenda/{p.stem[len(PREFIX):]}/": p.read_text()
        for p in FIXTURES.glob(f"{PREFIX}*.html")
    }


def _events(rotown=True):
    return build_events(
        (FIXTURES / "maassilo_agenda.html").read_text(),
        json.loads((FIXTURES / "maassilo_api.json").read_text()),
        _details(),
        (FIXTURES / "rotown_home.html").read_text() if rotown else None,
        TODAY,
    )


def _by_title(fragment: str):
    return next(e for e in _events() if fragment.lower() in e.title.lower())


def test_own_agenda_cards_with_inferred_year():
    items = parse_agenda((FIXTURES / "maassilo_agenda.html").read_text(), TODAY)
    assert len(items) >= 5
    assert next(i for i in items if i["title"] == "Megarave")["date"] == dt.date(2026, 10, 24)
    assert any(i["date"].year == 2027 for i in items)  # "9 jan" → next year


def test_detail_info_block():
    info = parse_detail((FIXTURES / "maassilo_detail_megarave.html").read_text())
    assert info["tijd"] == "13:00 - 22:00"
    assert info["prijs"] == "vanaf 20,-"
    mega = _by_title("Megarave")
    assert (mega.start_time, mega.price) == (dt.time(13, 0), "20€")
    assert _by_title("Gökhan").price == "59,90€"


def test_category_from_maassilo_genre_taxonomy():
    assert _by_title("Megarave").category_slugs == ["club"]           # techno
    assert _by_title("Unresolved").category_slugs == ["club"]         # hardstyle
    assert _by_title("Gökhan").category_slugs == ["pop"]              # concert
    assert _by_title("Broederliefde").category_slugs == ["pop"]       # hiphop
    assert "Now&Wow" in _by_title("Herr Zimmerman").annotations


def test_rotown_programmed_shows_at_maassilo_are_included():
    own = _events(rotown=False)
    both = _events()
    assert len(both) > len(own)
    tram = _by_title("Tramhaus")
    assert tram.category_slugs == ["pop"]
    assert tram.price == "24,50€" and tram.start_time == dt.time(20, 0)
    assert tram.source_url.startswith("https://www.rotown.nl/agenda/")
    assert tram.external_id.startswith("rotown:")
    assert "Rotown presents" in tram.annotations
    # Only Maassilo shows from Rotown's list.
    assert not any(e.title == "Turin Brakes" for e in both)


def test_ids_unique_and_dates_upcoming():
    events = _events()
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))
    assert all(e.start_date >= TODAY for e in events)
