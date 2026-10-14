import datetime as dt
from pathlib import Path

from cartelera.scrapers.ekko import BASE_URL, build_events, parse_detail, parse_list, resolve_date

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 14)
DETAIL_PREFIX = "ekko_detail_"


def _rows():
    return parse_list((FIXTURES / "ekko_agenda.html").read_text(), TODAY)


def _details():
    return {
        f"{BASE_URL}/event/{p.stem[len(DETAIL_PREFIX):]}/": p.read_text()
        for p in FIXTURES.glob(f"{DETAIL_PREFIX}*.html")
    }


def _events():
    return build_events(_rows(), _details())


def _by_slug(slug: str):
    return next(e for e in _events() if e.external_id == slug)


def test_list_keeps_own_concert_and_club_programme():
    rows = _rows()
    assert len(rows) == 62
    slugs = {r["slug"] for r in rows}
    # Off-site shows presented by EKKO (De Kromme Haring, ACU, Jacobikerk).
    assert not slugs & {"coaster", "flora-hibberd", "lezard", "ebbb", "my-first-time", "charlie-cunningham"}
    # "overig"-only items: the pop quiz and a cabaret night.
    assert not any("popquiz" in s or "cabaret" in s for s in slugs)
    # "Eten in EKKO" is not an event.
    assert all("/event/" in r["url"] for r in rows)
    ids = [r["slug"] for r in rows]
    assert len(ids) == len(set(ids))


def test_dates_and_years():
    rows = {r["slug"]: r for r in _rows()}
    assert rows["fenne"]["date"] == dt.date(2026, 10, 17)
    assert rows["alice-olsthoorn-1"]["date"] == dt.date(2027, 1, 15)
    assert resolve_date(5, 1, None, dt.date(2026, 12, 20)) == dt.date(2027, 1, 5)
    assert resolve_date(20, 12, None, dt.date(2027, 1, 5)) == dt.date(2026, 12, 20)
    assert resolve_date(26, 2, "27", TODAY) == dt.date(2027, 2, 26)


def test_categories_from_type_filter():
    rows = {r["slug"]: r for r in _rows()}
    assert rows["fenne"]["categories"] == ["pop"]
    assert rows["zora-2-year-anniversary"]["categories"] == ["club"]
    assert set(rows["le-guess-who-2026"]["categories"]) == {"pop", "club"}
    assert rows["wildgroei"]["categories"] == ["club"]


def test_detail_time_and_price():
    fenne = _by_slug("fenne")
    assert fenne.start_time == dt.time(20, 0) and fenne.price == "15,50€"
    assert fenne.title == "FENNE + Sophie Koole"
    zora = _by_slug("zora-2-year-anniversary")
    assert zora.start_time == dt.time(23, 30) and zora.price == "9€"
    assert _by_slug("club-fataal").price == "sold-out"
    assert _by_slug("popronde-2026").price == "free"
    # Free reservation, door price stated ("Aan de deur altijd €5,50").
    assert _by_slug("diep-in-de-groef-233").price == "5,50€"
    # Festival day tickets picked by weekday.
    assert _by_slug("echoes-from-the-dungeon-fest-iii").price == "36,50€"
    assert _by_slug("echoes-from-the-dungeon-fest-iii-2").price == "51,50€"
    # "Tickets via Le Guess Who?" — no price stated.
    assert _by_slug("le-guess-who-2026").price is None


def _detail(location: str, button: str) -> str:
    return f"""
    <div class="uppercase leading-tight"><div>Aanvang</div><div>20:00</div></div>
    <div class="uppercase leading-tight"><div>Locatie</div><div><a><button>{location}</button></a></div></div>
    <div class="flex flex-col"><a href="x"><button><span><span>{button}</span></span>
      <span>€ 12</span></button></a><div class="uppercase mt-2">incl. servicekosten</div></div>
    """


def test_cancelled_and_offsite_details_are_dropped():
    rows = [r for r in _rows() if r["slug"] == "fenne"]
    url = rows[0]["url"]
    (ev,) = build_events(rows, {url: _detail("EKKO", "Koop tickets")})
    assert ev.price == "12€" and ev.start_time == dt.time(20, 0)
    assert build_events(rows, {url: _detail("ACU", "Koop tickets")}) == []
    assert build_events(rows, {url: _detail("EKKO", "Geannuleerd")}) == []
    assert parse_detail(_detail("EKKO", "Uitverkocht"), rows[0]["date"])["price"] == "sold-out"


def test_every_fixture_detail_yields_a_time():
    events = [e for e in _events() if f"{BASE_URL}/event/{e.external_id}/" in _details()]
    assert len(events) == 8
    assert all(e.start_time for e in events)
