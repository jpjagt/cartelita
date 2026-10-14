import datetime as dt
from dataclasses import replace
from pathlib import Path

import pytest

from cartelera.scrapers.tivolivredenburg import (
    Detail,
    ListItem,
    build_event,
    categorize,
    exclusion_reason,
    has_next_page,
    parse_detail,
    parse_genre_tree,
    parse_list,
)

FIXTURES = Path(__file__).parent / "fixtures"
AGENDA = (FIXTURES / "tivolivredenburg_agenda.html").read_text()


def _detail(name: str) -> Detail:
    return parse_detail((FIXTURES / f"tivolivredenburg_detail_{name}.html").read_text())


@pytest.fixture(scope="module")
def tree():
    return parse_genre_tree(AGENDA)


def _item(genres: list[str], **kw) -> ListItem:
    base = dict(
        external_id="1", url="https://www.tivolivredenburg.nl/agenda/1/x-01-01-2027",
        title="X", genres=genres, date=dt.date(2027, 1, 8),
    )
    base.update(kw)
    return ListItem(**base)


def test_genre_tree_maps_subgenres_to_their_group(tree):
    assert tree["klassiek"][0] == "klassiek"
    assert tree["kamermuziek"] == ("klassiek", "Kamermuziek")
    assert tree["metal-punk-heavy"][0] == "pop-rock"
    # Cards use the ?sf_genre= slug, which can differ from data-term_id.
    assert tree["hiphop-rb-1"][0] == "pop-rock"
    assert tree["house-techno"][0] == "dance-by-night"
    assert tree["turks"][0] == "global"
    for group in ("jazz", "familie", "kennis-debat", "comedy"):
        assert tree[group][0] == group


def test_list_page_cards(tree):
    items = parse_list(AGENDA)
    assert len(items) == 20
    assert len({i.external_id for i in items}) == 20
    for i in items:
        assert i.url.startswith("https://www.tivolivredenburg.nl/agenda/")
        assert i.title
        assert i.date in (dt.date(2026, 10, 14), dt.date(2026, 10, 15))
    sportivo = next(i for i in items if i.title == "Gruppo Sportivo")
    assert sportivo.external_id == "36172076"
    assert sportivo.genres == ["pop-rock", "classic-pop-60s-90s", "nederlands"]
    assert has_next_page(AGENDA, 1)
    assert not has_next_page(AGENDA, 2)


def test_categorize(tree):
    assert categorize(["klassiek", "kamermuziek"], tree) == (["classical"], ["Kamermuziek"])
    assert categorize(["pop-rock", "soul-funk-jazz", "jazz"], tree)[0] == ["pop", "jazz"]
    assert categorize(["dance-by-night", "house-techno"], tree)[0] == ["club"]
    assert categorize(["global", "pop-rock"], tree)[0] == ["pop", "folk"]
    # Sub-genre only (no parent term on the card) still resolves.
    assert categorize(["kamermuziek", "oude-muziek"], tree)[0] == ["classical"]
    # Family concerts go to kids only.
    assert categorize(["pop-rock", "familie"], tree)[0] == ["kids"]
    # Talks / comedy / untagged are not music programme.
    assert categorize(["kennis-debat"], tree)[0] == []
    assert categorize(["comedy"], tree)[0] == []
    assert categorize([], tree)[0] == []


def test_list_level_exclusions(tree):
    items = {i.title: i for i in parse_list(AGENDA)}
    assert exclusion_reason(items["KLANKKEUKEN"], None, tree)  # no genre
    assert exclusion_reason(items["Gruppo Sportivo"], None, tree) is None


def test_classical_tiers_and_doors_vs_start(tree):
    d = _detail("classical_tiers")
    assert d.doors == dt.time(19, 15)
    assert d.start_times == [dt.time(20, 15)]  # "Aanvang", not the JSON-LD doors time
    assert d.location == "Grote zaal" and d.in_house
    # Rang 1/2/3 Regulier 43/36/31,50 (Onder 30 skipped): < 2x → highest.
    assert d.price == "43€"
    ev = build_event(_item(["klassiek", "symfonisch"]), d, tree)
    assert ev.start_time == dt.time(20, 15)
    assert ev.category_slugs == ["classical"]
    assert ev.annotations == ["Grote zaal", "Symfonisch"]
    assert ev.price == "43€"


def test_sold_out_wins_and_decimal_price(tree):
    d = _detail("sold_out")
    assert d.price == "26,50€" and d.sold_out
    assert d.end_time == dt.time(22, 45)
    ev = build_event(_item(["pop-rock"]), d, tree)
    assert ev.price == "sold-out"
    assert ev.end_date == ev.start_date and ev.end_time == dt.time(22, 45)


def test_zero_price_is_free(tree):
    d = _detail("lunchconcert")
    assert d.price == "free"
    assert d.start_times == [dt.time(12, 30)]


def test_per_act_set_times_start_at_first_act():
    d = _detail("act_times")
    assert d.doors == dt.time(19, 0)
    assert d.start_times == [dt.time(19, 45)]
    assert d.price == "51€"


def test_family_sessions_from_programme_prose(tree):
    d = _detail("family_sessions")
    assert d.start_times == [dt.time(10, 0), dt.time(11, 30), dt.time(13, 0)]
    ev = build_event(_item(["klassiek", "familie"]), d, tree)
    assert ev.start_time == dt.time(10, 0)
    assert ev.start_times == d.start_times
    assert ev.category_slugs == ["kids"]


def test_from_price_without_tiers():
    assert _detail("from_price").price == "48€"


def test_club_night_doors_only_and_past_midnight_end(tree):
    d = _detail("club_doors")
    assert d.start_times == [] and d.doors == dt.time(22, 0)
    # (Park 6 itself is an excluded series; drop it to test the timing.)
    ev = build_event(_item(["dance-by-night"]), replace(d, series_paths=[]), tree)
    assert ev.start_time == dt.time(22, 0)
    assert ev.end_time == dt.time(1, 0)
    assert ev.end_date == ev.start_date + dt.timedelta(days=1)
    assert ev.price == "free"


@pytest.mark.parametrize("name,genres,reason", [
    ("offsite_dbs", ["pop-rock", "metal-punk-heavy"], "off-site"),
    ("vrije_ruimte", ["roots-blues-americana"], "non-programme series"),
    ("club_doors", ["dance-by-night"], "non-programme series"),
    ("cancelled", ["pop-rock"], "cancelled"),
])
def test_detail_exclusions(tree, name, genres, reason):
    d = _detail(name)
    assert exclusion_reason(_item(genres), d, tree).startswith(reason)
    assert build_event(_item(genres), d, tree) is None


def test_kept_events_are_fully_populated(tree):
    items = {i.external_id: i for i in parse_list(AGENDA)}
    ev = build_event(items["36172076"], _detail("sold_out"), tree)
    assert ev.title == "Gruppo Sportivo"
    assert ev.start_date == dt.date(2026, 10, 14)
    assert ev.start_time == dt.time(20, 30)
    assert ev.external_id == "36172076"
    assert ev.source_url == items["36172076"].url
    assert ev.category_slugs == ["pop"]
    assert ev.annotations == ["Pandora", "Classic Pop (60's-90's)", "Nederlands"]
    assert ev.image_url and ev.description
