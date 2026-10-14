import datetime as dt
from pathlib import Path

from cartelera.scrapers.rotown import parse_home

FIXTURE = Path(__file__).parent / "fixtures" / "rotown_home.html"


def _events():
    return parse_home(FIXTURE.read_text())


def _by_title(fragment: str):
    return next(e for e in _events() if fragment.lower() in e.title.lower())


def test_parses_rotown_programme():
    events = _events()
    assert len(events) >= 60
    for e in events:
        assert e.title
        assert e.start_date >= dt.date(2026, 10, 14)
        assert e.source_url.startswith("https://www.rotown.nl/agenda/")
        assert e.category_slugs in (["pop"], ["club"])


def test_shows_at_other_venues_are_dropped():
    titles = {e.title for e in _events()}
    # Rotown-promoted shows at Maassilo, Annabel, LantarenVenster, V11, MONO,
    # Roodkapje West: owned by those venues' own sources (or not covered).
    for t in ("Chef'Special", "Frazey Ford", "Sophie Hutchings", "Tanzana",
              "SABORA at MONO", "Velocity Made Good", "Belle & Sebastian"):
        assert t not in titles


def test_free_cafe_programme_is_dropped():
    titles = {e.title for e in _events()}
    for t in ("Spelletjesavond", "Crafternoon", "Open Mic Night",
              "Rock 'N Rommel", "Records, DJs & Drinks"):
        assert t not in titles


def test_rotown_nights_series_is_club_else_pop():
    assert _by_title("Friday Indie Fix").category_slugs == ["club"]
    assert _by_title("Peach Club").category_slugs == ["club"]
    assert _by_title("Turin Brakes").category_slugs == ["pop"]
    club = [e for e in _events() if e.category_slugs == ["club"]]
    assert len(club) >= 10
    assert all("ROTOWN NIGHTS" in e.annotations for e in club)


def test_price_and_time():
    events = _events()
    assert all(e.price for e in events)
    assert _by_title("Turin Brakes").price == "25,50€"
    assert _by_title("Turin Brakes").start_time == dt.time(20, 30)
    assert _by_title("Genesis Owusu").price == "sold-out"
    assert _by_title("DIY DJ Party").price == "7€"           # "Deurverkoop: €7"
    assert _by_title("DIY DJ Party").start_time is None       # 23:59 placeholder


def test_external_ids_unique_and_featured_duplicates_collapsed():
    events = _events()
    ids = [e.external_id for e in events]
    assert len(ids) == len(set(ids))
    assert sum(1 for e in events if e.title == "After Elmer") == 1
    # Two Lucky Fonz III nights are two occurrences.
    assert sum(1 for e in events if e.title == "Lucky Fonz III") == 2


def test_club_nights_take_the_door_price():
    from cartelera.scrapers.rotown import door_price, with_door_price

    detail = (FIXTURE.parent / "rotown_detail_bangers-1.html").read_text()
    assert door_price(detail) == "Deur: €7,00"
    bangers = _by_title("BANGERS")
    assert bangers.price == "5€"                      # online "vanaf € 5,00"
    assert with_door_price(bangers, detail).price == "7€"
    sold = _by_title("Genesis Owusu")
    assert with_door_price(sold, detail).price == "sold-out"
