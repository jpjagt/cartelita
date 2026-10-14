import datetime as dt
from pathlib import Path

from cartelera.scrapers.de_helling import card_ids, detail_price, parse_agenda

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text()


def _events():
    return parse_agenda(
        _read("de_helling_agenda.html"),
        card_ids(_read("de_helling_label_club.html")),
        card_ids(_read("de_helling_label_cafe.html")),
    )


def _by_title(fragment: str):
    return next(e for e in _events() if fragment in e.title)


def test_parses_all_cards_except_cancelled():
    events = _events()
    # 66 cards, one "Afgelast" (Bartofso) dropped.
    assert len(events) == 65
    assert not any(e.title == "Bartofso" for e in events)


def test_fields_populated():
    for ev in _events():
        assert ev.title and "&#" not in ev.title
        assert ev.source_url.startswith("https://dehelling.nl/agenda/")
        assert ev.start_time is not None
        assert ev.image_url
        assert ev.category_slugs in (["pop"], ["club"])
    ids = [e.external_id for e in _events()]
    assert len(ids) == len(set(ids))


def test_category_from_the_venue_club_filter():
    events = _events()
    assert sum(e.category_slugs == ["club"] for e in events) == 16
    assert _by_title("Paardenrave").category_slugs == ["club"]
    assert _by_title("Ozric Tentacles").category_slugs == ["pop"]
    # Cards on the cafe filter would be dropped.
    html = _read("de_helling_agenda.html")
    some_id = sorted(card_ids(html))[0]
    assert len(parse_agenda(html, set(), {some_id})) == 64


def test_price_and_sold_out_from_event_status_only():
    events = _events()
    assert sum(1 for e in events if e.price) >= 60
    jh = _by_title("Jhariah")
    assert jh.price == "19,50€" and jh.start_time == dt.time(20, 15)
    assert _by_title("IST IST").price == "sold-out"
    # JSON-LD availability says SoldOut but the venue is still selling.
    assert _by_title("Ozric Tentacles").price == "29,50€"


def test_genre_tags_are_annotations():
    jh = _by_title("Jhariah")
    assert jh.annotations == ["emo", "Punk", "Hiphop"]


def test_detail_price_for_free_events():
    assert detail_price(_read("de_helling_detail_free.html")) == "free"
    assert detail_price(_read("de_helling_detail_paid.html")) == "29,50€"
    assert detail_price(_read("de_helling_detail_noprice.html")) is None
