import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers.bird import SITE_URL, is_elsewhere, parse_documents

FIXTURE = Path(__file__).parent / "fixtures" / "bird_api.json"


def _docs():
    return json.loads(FIXTURE.read_text())["results"]


def _events():
    return parse_documents(_docs())


def _by_title(fragment: str):
    return next(e for e in _events() if fragment.lower() in e.title.lower())


def test_parses_programme_events():
    events = _events()
    assert len(events) >= 30
    for e in events:
        assert e.title
        assert e.start_date >= dt.date(2026, 10, 14)
        assert e.source_url.startswith(f"{SITE_URL}/event/")
        assert e.category_slugs in (["jazz"], ["pop"], ["club"])
        assert e.image_url


def test_category_from_bird_main_category_and_jazz_genre():
    # main_category "club" → club; "live" + BIRD's jazz genre → jazz;
    # "live" without it (soul/hip-hop/folk) → pop.
    assert _by_title("Lovumba").category_slugs == ["club"]
    assert _by_title("New Jazz Underground").category_slugs == ["jazz"]
    assert _by_title("Trixie Whitley").category_slugs == ["pop"]
    cats = {c for e in _events() for c in e.category_slugs}
    assert cats == {"jazz", "pop", "club"}


def test_mavis_bar_sessions_and_food_are_not_programme():
    titles = [e.title for e in _events()]
    assert not any("Pass da Jazz" in t for t in titles)
    mavis = [d for d in _docs() if any(
        (m.get("main_category") or {}).get("uid") == "mavis"
        for m in d["data"]["main_categories"])]
    assert mavis  # the fixture has them; they're filtered


def test_shows_bird_presents_at_other_venues_are_dropped():
    elsewhere = [d for d in _docs() if is_elsewhere(d)]
    uids = {d["uid"] for d in elsewhere}
    assert "gallowstreet-at-annabel-13-12-2026" in uids          # uid + text
    assert "lizz-wright-24-10-26" in uids                        # "At De Doelen"
    assert "josylvio-03-12-2026" in uids                         # "niet bij BIRD"
    assert "zwangere-guy-03-12-2026" in uids                     # "at Maassilo"
    titles = {e.title for e in _events()}
    for t in ("Gallowstreet", "Lizz Wright", "Myles Sanko", "Eek-A-Mouse"):
        assert not any(t.lower() in x.lower() for x in titles)


def test_times_come_from_start_label_or_range():
    assert _by_title("Lovumba").start_time == dt.time(23, 0)
    assert _by_title("Trixie Whitley").start_time == dt.time(20, 30)
    # "talk 19:00 | concert 20:30" → the concert start
    assert _by_title("Collier plays Coltrane").start_time == dt.time(20, 30)
    assert all(e.start_time for e in _events())


def test_price_coverage_and_normalization():
    events = _events()
    assert sum(1 for e in events if e.price) >= 0.9 * len(events)
    assert _by_title("Lovumba").price == "14,95€"          # "V.A. €14,95"
    assert _by_title("Infinity Song").price == "sold-out"  # "UITVERKOCHT"
    assert _by_title("Gabriel Cassaro").price == "free"    # "GRATIS"
    assert _by_title("Melodyne").price == "11€"            # "V.A. €11,-"


def test_genres_go_to_annotations_and_ids_are_unique():
    lov = _by_title("Lovumba")
    assert "afro" in lov.annotations
    assert "club" not in lov.annotations
    ids = [e.external_id for e in _events()]
    assert all(ids) and len(ids) == len(set(ids))
