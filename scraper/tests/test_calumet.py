import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers.calumet import parse_feed

FIXTURE = Path(__file__).parent / "fixtures" / "calumet_feed.json"

# The fixture was saved on 2026-08-18 via `GET .../events/feed?...&from=2025-01-01`
# (the un-parameterized feed Calumet's scraper actually calls returns only
# today-or-later occurrences, which on the save date was a single event — too
# thin to test against, so the fixture carries the full history instead: 66
# occurrences of 38 events, 2025-11-11 through 2026-08-18). The parser filters
# to `today`-or-later relative to an injected `today` so the test is
# deterministic against the fixture regardless of when it's run.
TODAY = dt.date(2026, 6, 1)


def _events():
    return parse_feed(FIXTURE.read_text(), today=TODAY)


def test_parses_the_expected_window():
    # 21 occurrences from 2026-06-01 onward in the saved fixture.
    assert len(_events()) == 21


def test_events_have_valid_date_title_url_category():
    for ev in _events():
        assert isinstance(ev.start_date, dt.date)
        assert ev.start_date >= TODAY
        assert ev.title and ev.title.strip()
        assert ev.source_url.startswith("https://esora.app/hy/yerevan/events/")
        assert ev.category_slugs in (["club"], ["folk"])


def test_category_split_matches_the_real_programme():
    # Esora's own `category` field (clubbing vs live_music/music/social) is
    # the discriminator — not a guess from the title. The fixture window has
    # a real mix of both; a scraper that returned only one category would be
    # a sign the discriminator broke.
    slugs = [ev.category_slugs[0] for ev in _events()]
    assert slugs.count("club") == 10
    assert slugs.count("folk") == 11


def test_no_event_is_ever_labeled_jazz():
    # The venue's historical programme (checked in full: 66 occurrences)
    # never mentions jazz. Regression guard against reintroducing the
    # initially-hypothesized ["folk", "jazz"] split without real evidence.
    for ev in _events():
        assert "jazz" not in ev.category_slugs


def test_external_ids_are_per_occurrence_unique():
    ids = [ev.external_id for ev in _events()]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_repeat_title_keeps_one_event_page_but_distinct_occurrences():
    # Several acts/nights recur (e.g. "Electro Almaza Tuesdays", "Cheyenne",
    # "Sasha Lenivec") — same event page, several dated occurrences.
    events = _events()
    by_url: dict[str, list] = {}
    for ev in events:
        by_url.setdefault(ev.source_url, []).append(ev)
    repeated = [evs for evs in by_url.values() if len(evs) > 1]
    assert repeated, "expected at least one recurring night with multiple dates"
    for evs in repeated:
        dates = {ev.start_date for ev in evs}
        assert len(dates) == len(evs)
        assert len({ev.external_id for ev in evs}) == len(evs)


def test_prices_follow_the_convention():
    for ev in _events():
        assert ev.price is None or (isinstance(ev.price, str) and ev.price.strip())


def test_free_entry_is_normalized():
    free_titles = {ev.title for ev in _events() if ev.price == "free"}
    assert free_titles, "expected at least one normalized 'free' price in the window"
    for ev in _events():
        if ev.price:
            assert "no entrance fee" not in ev.price.lower()
            assert "free entrance" not in ev.price.lower()


def test_minor_amd_spread_collapses_to_the_high_value():
    # "5000–7000 AMD" (hi < 2x lo) should collapse to "7000 AMD", not a range.
    events = parse_feed(FIXTURE.read_text(), today=dt.date(2026, 3, 1))
    matched = [ev for ev in events if ev.start_date == dt.date(2026, 3, 28)]
    assert matched
    assert matched[0].price == "7000 AMD"


def test_language_is_never_inferred():
    for ev in _events():
        assert ev.language is None


def test_translations_carry_ru_and_en_when_present():
    # Esora hasn't machine-translated a few recently-ingested events yet
    # (empty i18n); real signal, not a bug — don't require translations
    # unconditionally, but every translation that exists must be well-formed.
    for ev in _events():
        for t in ev.translations:
            assert t.lang in ("ru", "en")
            assert t.title and t.title.strip()
            assert t.source_url.startswith(f"https://esora.app/{t.lang}/yerevan/events/")
    assert any(ev.translations for ev in _events())


def test_annotations_do_not_leak_the_category_discriminator():
    for ev in _events():
        assert "clubbing" not in ev.annotations
        assert "live_music" not in ev.annotations
        assert not set(ev.category_slugs) & set(ev.annotations)


def test_placeholder_tags_are_dropped_from_annotations():
    # esora fills in "live_music_other"/"clubbing_other" when it has no real
    # genre signal; these aren't informative and shouldn't show up.
    for ev in _events():
        assert "live_music_other" not in ev.annotations
        assert "clubbing_other" not in ev.annotations


def test_past_occurrences_are_filtered():
    events = parse_feed(FIXTURE.read_text(), today=dt.date(2026, 8, 18))
    assert events
    assert all(ev.start_date >= dt.date(2026, 8, 18) for ev in events)
    assert not parse_feed(FIXTURE.read_text(), today=dt.date(2027, 1, 1))


def test_disabled_entities_are_skipped():
    data = json.loads(FIXTURE.read_text())
    occs = data["entities"]["eventOccurrences"]
    first_occ_id = next(
        occ_id
        for occ_id in data["result"]["eventOccurrenceIds"]
        if occs[occ_id]["startDate"] >= "2026-06-01"
    )
    occs[first_occ_id]["disabledAt"] = "2026-08-18T00:00:00.000Z"
    events = parse_feed(json.dumps(data), today=TODAY)
    assert len(events) == 20
