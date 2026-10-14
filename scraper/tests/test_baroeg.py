import datetime as dt
from pathlib import Path

from cartelera.scrapers.baroeg import parse_agenda

FIXTURE = Path(__file__).parent / "fixtures" / "baroeg_agenda.html"


def _events():
    return parse_agenda(FIXTURE.read_text())


def _by_title(fragment: str):
    return next(e for e in _events() if fragment.lower() in e.title.lower())


def test_parses_agenda_cards():
    events = _events()
    assert len(events) >= 25
    for e in events:
        assert e.title and "  " not in e.title
        assert e.start_date >= dt.date(2026, 10, 14)
        assert e.start_time is not None
        assert e.source_url.startswith("https://baroeg.nl/productie/")
        assert e.category_slugs in (["alternative"], ["club"])


def test_night_programme_is_club_and_genres_are_annotations():
    assert _by_title("Berzerk IV").category_slugs == ["club"]          # "dance night"
    assert _by_title("PRSPCT").category_slugs == ["club"]              # "Nachtprogramma"
    nile = _by_title("Nile + Redsphere")
    assert nile.category_slugs == ["alternative"]
    assert nile.annotations == ["death"]
    assert not any("dance night" in a for e in _events() for a in e.annotations)


def test_cancelled_and_off_site_shows_are_dropped():
    titles = " | ".join(e.title for e in _events())
    assert "Backfire" not in titles       # "Geannuleerd"
    assert "SoundVille" not in titles     # "Baroeg On Tour @ SoundVille"


def test_price_is_the_door_price_and_combi_passes_ignored():
    events = _events()
    assert sum(1 for e in events if e.price) >= 0.9 * len(events)
    assert _by_title("Benediction").price == "27,50€"    # Vvk 25 / Entree 27,50
    assert _by_title("DDD XXIV Day 1").price == "32,50€"  # not the 60€ combi
    assert _by_title("Emo Night").price == "16€"          # "(400 stuks)" isn't a price
    assert _by_title("Benediction").start_date == dt.date(2026, 10, 18)
    assert _by_title("Benediction").start_time == dt.time(15, 0)


def test_external_ids_unique():
    ids = [e.external_id for e in _events()]
    assert len(ids) == len(set(ids))
