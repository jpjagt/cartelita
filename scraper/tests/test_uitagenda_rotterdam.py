import datetime as dt
import json
from collections import Counter
from pathlib import Path

from cartelera.scrapers.uitagenda_rotterdam import (
    BASE_URL,
    LOCATION_VENUES,
    _title,
    dance_ids,
    parse_productions,
)

FIXTURES = Path(__file__).parent / "fixtures"
THEATER = json.loads((FIXTURES / "uitagenda_rotterdam_theater.json").read_text())
DANCE = json.loads((FIXTURES / "uitagenda_rotterdam_dance.json").read_text())
LOCATIONS = [
    json.loads((FIXTURES / f"uitagenda_rotterdam_location_{i}.json").read_text())
    for i in (49556, 49376)
]
WHITELIST = {"theater-rotterdam", "theater-walhalla", "mooi-weer", "hofplein"}


def _events():
    return parse_productions(THEATER, dance_ids(DANCE), LOCATIONS)


def _items():
    return THEATER["pagedList"]["items"]


def test_parses_many_events_only_for_whitelisted_venues():
    events = _events()
    assert len(events) > 400
    assert {e.venue_slug for e in events} == WHITELIST
    # The fixture also carries other venues' items (Zuidplein, Rotown, …).
    assert any(
        it["location"] and it["location"]["id"] not in LOCATION_VENUES for it in _items()
    )


def test_maaspodium_is_not_whitelisted():
    # Maaspodium is Maas theater en dans' own stage, owned by the `maas` source.
    assert 49504 not in LOCATION_VENUES
    assert any(it["location"] and it["location"]["id"] == 49504 for it in _items())


def test_events_have_dates_titles_urls_and_known_categories():
    for ev in _events():
        assert dt.date(2026, 10, 1) <= ev.start_date <= dt.date(2027, 12, 31)
        assert ev.title and not ev.title.endswith(("/", "|"))
        assert ev.source_url.startswith(f"{BASE_URL}/agenda/")
        assert ev.category_slugs
        assert set(ev.category_slugs) <= {"theater", "dance", "kids"}
        assert not {"theater", "dance"} <= set(ev.category_slugs)
        assert ev.price in (None, "sold-out")
        assert ev.language is None


def test_time_coverage():
    events = _events()
    assert sum(e.start_time is not None for e in events) / len(events) > 0.95


def test_external_ids_unique_per_occurrence():
    ids = [e.external_id for e in _events()]
    assert len(ids) == len(set(ids))


def test_dance_comes_from_the_agendas_dance_landing():
    events = _events()
    dance = [e for e in events if "dance" in e.category_slugs]
    assert len(dance) > 30
    assert {e.venue_slug for e in dance} <= {"theater-rotterdam", "theater-walhalla"}
    ndt = next(e for e in events if e.title.startswith("Blast a universe"))
    assert ndt.category_slugs == ["dance"]
    toneel = next(e for e in events if e.title.startswith("Romeo en Julia"))
    assert toneel.category_slugs == ["theater"]


def test_youth_venue_and_kids_genre_mark_kids():
    events = _events()
    assert all("kids" in e.category_slugs for e in events if e.venue_slug == "hofplein")
    alice = next(e for e in events if e.title.startswith("Alice in Wonderland"))
    assert "kids" in alice.category_slugs


def test_non_programme_genres_are_dropped():
    excluded = {
        f"{it['parentId']}@{it['key']}" for it in _items()
        if {g["key"] for g in it["genres"]} & {"culinair", "workshop", "evenementen", "expo"}
    }
    assert excluded  # e.g. the "Club Metro" dinner shows tagged culinair
    assert not excluded & {e.external_id for e in _events()}


def test_same_show_entered_twice_is_deduped():
    events = _events()
    per_slot = Counter(
        (e.start_date, e.start_time) for e in events
        if e.venue_slug == "theater-walhalla" and e.title.lower().startswith("christmas inc")
    )
    assert per_slot and max(per_slot.values()) == 1
    # TR lists its FUTURE VOICES double bill both as a whole and per part.
    fv = [e for e in events if e.title.startswith("FUTURE VOICES")]
    assert len(fv) == 1


def test_multiple_sessions_on_one_day_become_start_times():
    laqua_like = [e for e in _events() if len(e.start_times) > 1]
    assert laqua_like
    for e in laqua_like:
        assert e.start_time == min(e.start_times)


def test_placeholder_0700_is_time_unknown():
    wh = [e for e in _events() if e.title.startswith("Wuthering Heights")]
    assert wh
    assert all(e.start_time != dt.time(7, 0) for e in wh)


def test_title_rejoins_age_indication():
    assert _title({"title": "Dag poes /", "ageIndication": "4+"}) == "Dag poes / 4+"
    assert _title({"title": "Carmen", "ageIndication": "must die"}) == "Carmen (must die)"
    assert _title({"title": "Rebel", "ageIndication": ""}) == "Rebel"


def test_genre_less_items_count_only_at_single_discipline_houses():
    events = _events()
    # Mooi Weer's "Toneelstuk Oedipus" carries no genre at all: kept as theater.
    oedipus = [e for e in events if e.title == "Toneelstuk Oedipus"]
    assert len(oedipus) >= 5
    assert all(e.venue_slug == "mooi-weer" and e.category_slugs == ["theater"] for e in oedipus)
    # At Theater Rotterdam genre-less, non-dance items (a concert) are dropped.
    assert not any(e.title.startswith("Belle & Sebastian") for e in events)
    # Without the location pages the genre-less items are simply absent.
    bare = parse_productions(THEATER, dance_ids(DANCE))
    assert not any(e.title == "Toneelstuk Oedipus" for e in bare)
