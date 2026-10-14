import datetime as dt
import json
from pathlib import Path

from cartelera.scrapers.annabel import parse_posts

FIXTURE = Path(__file__).parent / "fixtures" / "annabel_posts.json"
TODAY = dt.date(2026, 10, 14)


def _posts():
    return json.loads(FIXTURE.read_text())


def _events():
    return parse_posts(_posts(), TODAY)


def _by_title(fragment: str):
    return next(e for e in _events() if fragment.lower() in e.title.lower())


def test_parses_upcoming_posts():
    events = _events()
    assert len(events) >= 15
    for e in events:
        assert e.title and "&#" not in e.title
        assert e.start_date >= TODAY
        assert e.source_url.startswith("https://annabel.nu/")
        assert e.image_url
    assert parse_posts(_posts(), dt.date(2030, 1, 1)) == []


def test_category_from_annabels_wp_category():
    assert _by_title("Frazey Ford").category_slugs == ["pop"]        # concert
    assert _by_title("NEMS Unleashed").category_slugs == ["club"]    # clubnacht
    assert _by_title("Elida Almeida").category_slugs == ["pop", "club"]  # both
    post = dict(_posts()[0], class_list=["post", "category-terras"])
    assert parse_posts([post], TODAY) == []


def test_time_and_price():
    events = _events()
    assert all(e.start_time for e in events)
    assert all(e.price for e in events)
    assert _by_title("NEMS Unleashed").start_time == dt.time(23, 0)   # "23:00 - 04:00"
    assert _by_title("Merol").start_time == dt.time(19, 0)            # "deuren open 19:00"
    assert _by_title("Splash").price == "33€"                         # "vanaf 33,-"
    assert _by_title("Merol").price == "33,75€"
    assert _by_title("Frazey Ford").price == "sold-out"               # Ticketstatus


def test_cancelled_posts_dropped_and_ids_unique():
    post = json.loads(json.dumps(_posts()[0]))
    post["acf"]["calendar"]["cancelled"] = True
    assert parse_posts([post], TODAY) == []
    ids = [e.external_id for e in _events()]
    assert len(ids) == len(set(ids))
    assert "live" not in _by_title("Kans").annotations
    assert "hip-hop" in _by_title("Kans").annotations
