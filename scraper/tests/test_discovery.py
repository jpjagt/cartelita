"""Opt-out venue discovery end to end: the real jazzin.amsterdam scraper (its
fetch stubbed) through run_one — venue creation, category growth, denylist,
slug collisions, health of new/quiet venues, and the rolling review issue."""
from __future__ import annotations
import datetime as dt
import logging

import pytest

from cartelera import health as h
from cartelera import health_ops
from cartelera.discovery import REVIEW_LABEL, review_title
from cartelera.models import Category, City, Event, List, ListVenue, ScrapeRun, Venue
from cartelera.run import run_one
from cartelera.scrapers import REGISTRY
from cartelera.scrapers import jazzin_amsterdam as jazzin
from cartelera.seed import seed

from tests.test_health_db import FakeTracker

TODAY = dt.date.today()
SLUG = jazzin.SOURCE_SLUG


def _item(venue: str, id_: int, *, days: int = 5, title: str | None = None,
          address: str = "Somestraat 1, 1011 AA Amsterdam", source: str = "submit") -> dict:
    return {"id": id_, "venue": venue, "title": title or f"Gig {id_}",
            "date": (TODAY + dt.timedelta(days=days)).isoformat(), "time": "20:30:00",
            "price": "€10", "site": f"https://example.org/{id_}", "address": address,
            "source": source}


@pytest.fixture()
def feed(session, monkeypatch):
    """The (category, item) pairs the stubbed jazzin API returns; tests set it."""
    seed(session)
    items: list[tuple[str, dict]] = []
    monkeypatch.setattr(jazzin, "fetch_items", lambda: list(items))
    return items


def _bimhuis(n: int = 12) -> list[tuple[str, dict]]:
    """Steady events at an override venue, so the source has a baseline."""
    return [("jazz", _item("Bimhuis", 1000 + i, days=3 + i)) for i in range(n)]


def _memberships(session, venue: Venue) -> set[tuple[str, str | None]]:
    rows = session.query(ListVenue).filter_by(venue_id=venue.id).all()
    cats = {c.id: c.slug for c in session.query(Category)}
    return {(session.get(List, r.list_id).slug, cats.get(r.whitelist_category_id)) for r in rows}


def test_discovery_creates_venue_memberships_and_categories(session, feed):
    feed[:] = _bimhuis() + [
        ("jazz", _item("Café de Muurbloem", 1, address="Bloemgracht 170, 1015 TV Amsterdam")),
        ("classical", _item("Café de Muurbloem", 2, address="Bloemgracht 170, 1015 TV Amsterdam")),
    ]
    gh = FakeTracker()
    r = run_one(session, SLUG, tracker=gh, today=TODAY)
    assert r.ok and r.verdict == h.HEALTHY, r.fired

    v = session.query(Venue).filter_by(slug="cafe-de-muurbloem").one()
    assert v.name == "Café de Muurbloem"
    assert v.address == "Bloemgracht 170, 1015 TV Amsterdam"
    assert v.city.slug == "amsterdam"
    assert v.discovered_by == SLUG
    assert {c.slug for c in v.categories} == {"jazz", "classical"}
    assert _memberships(session, v) == {("jazz", "jazz"), ("classical", "classical")}
    assert {e.title for e in v.events} == {"Gig 1", "Gig 2"}
    # lists are the amsterdam ones
    assert {session.get(List, lv.list_id).city_id
            for lv in session.query(ListVenue).filter_by(venue_id=v.id)} == {
        session.query(City).filter_by(slug="amsterdam").one().id}

    # reported: result, metrics, review issue
    assert r.new_venues == [{"slug": "cafe-de-muurbloem", "name": "Café de Muurbloem",
                             "address": "Bloemgracht 170, 1015 TV Amsterdam",
                             "categories": ["jazz", "classical"], "events": 2}]
    run = session.query(ScrapeRun).filter_by(source_slug=SLUG).one()
    assert run.metrics["new_venues"] == r.new_venues
    # a brand-new venue is a scope of its own, with nothing known: no rule fires
    assert run.metrics["venues"]["cafe-de-muurbloem"]["known_upcoming"] == 0
    assert run.metrics["fired"] == []


def test_discovered_venue_gains_a_category_later_and_is_not_new_again(session, feed):
    feed[:] = _bimhuis() + [("jazz", _item("Frascati", 1))]
    gh = FakeTracker()
    run_one(session, SLUG, tracker=gh, today=TODAY)
    feed[:] = _bimhuis() + [("jazz", _item("Frascati", 1)),
                            ("theater", _item("Frascati", 2, address="Nes 63, 1012 KD Amsterdam"))]
    r = run_one(session, SLUG, tracker=gh, today=TODAY)
    assert r.verdict == h.HEALTHY and r.new_venues == []
    v = session.query(Venue).filter_by(slug="frascati").one()
    assert {c.slug for c in v.categories} == {"jazz", "theater"}
    assert _memberships(session, v) == {("jazz", "jazz"), ("theater", "theater")}
    assert v.address == "Somestraat 1, 1011 AA Amsterdam"  # created once; not rewritten
    # gone from the jazz calendar later: memberships are never removed
    feed[:] = _bimhuis() + [("theater", _item("Frascati", 2))]
    run_one(session, SLUG, tracker=gh, today=TODAY)
    assert _memberships(session, v) == {("jazz", "jazz"), ("theater", "theater")}
    # one issue, opened by the first run only
    assert len(gh.issues) == 1


def test_denied_names_create_nothing(session, feed):
    feed[:] = _bimhuis() + [
        ("alternative", _item("Amsterdam", 1)),
        ("alternative", _item("Filmhuis Cavia", 2)),
        ("theater", _item("Comedytrain - Westergas - Grote Zaal", 3, source="toomler")),
    ]
    before = session.query(Venue).count()
    gh = FakeTracker()
    r = run_one(session, SLUG, tracker=gh, today=TODAY)
    assert r.ok and r.new_venues == []
    assert session.query(Venue).count() == before
    assert session.query(Event).count() == 12
    assert gh.issues == {}


def test_alias_merge_still_lands_on_the_override(session, feed):
    feed[:] = _bimhuis() + [("jazz", _item("Roode Bioscoop", 1))]
    r = run_one(session, SLUG, tracker=FakeTracker(), today=TODAY)
    assert r.new_venues == []
    v = session.query(Venue).filter_by(slug="de-roode-bioscoop").one()
    assert v.discovered_by is None
    assert [e.title for e in v.events] == ["Gig 1"]


def test_slug_owned_by_another_source_is_skipped_with_a_warning(session, feed, caplog):
    # "Jamboree" isn't a jazzin override, but its slug is the jamboree
    # source's venue (Barcelona): never touch it.
    feed[:] = _bimhuis() + [("jazz", _item("Jamboree", 1)), ("jazz", _item("Frascati", 2))]
    with caplog.at_level(logging.WARNING):
        r = run_one(session, SLUG, tracker=FakeTracker(), today=TODAY)
    assert r.ok
    jam = session.query(Venue).filter_by(slug="jamboree").one()
    assert jam.discovered_by is None and jam.city.slug == "barcelona"
    assert jam.events == []
    assert [v["slug"] for v in r.new_venues] == ["frascati"]
    assert "jamboree" in caplog.text and "skipped events" in caplog.text
    run = session.query(ScrapeRun).filter_by(source_slug=SLUG).one()
    assert set(run.metrics["refused_venues"]) == {"jamboree"}


def test_existing_venue_not_discovered_by_the_source_is_skipped(session, feed):
    # e.g. a venue of an archived scraper still in the DB
    ams = session.query(City).filter_by(slug="amsterdam").one()
    session.add(Venue(slug="frascati", name="Frascati (old)", city_id=ams.id))
    session.commit()
    feed[:] = _bimhuis() + [("theater", _item("Frascati", 1))]
    r = run_one(session, SLUG, tracker=FakeTracker(), today=TODAY)
    assert r.ok and r.new_venues == []
    v = session.query(Venue).filter_by(slug="frascati").one()
    assert v.name == "Frascati (old)" and v.events == [] and v.categories == []


def test_review_issue_opens_once_then_comments_then_reopens_when_closed(session, feed):
    gh = FakeTracker()
    feed[:] = _bimhuis()
    run_one(session, SLUG, tracker=gh, today=TODAY)
    assert gh.issues == {}                                    # nothing new: no issue

    feed[:] = _bimhuis() + [("jazz", _item("Frascati", 1))]
    run_one(session, SLUG, tracker=gh, today=TODAY)
    assert list(gh.issues) == [1]
    issue = gh.issues[1]
    assert issue["title"] == review_title(SLUG) == "jazzin-amsterdam: venues to review"
    assert issue["labels"] == [REVIEW_LABEL]
    for text in ("Frascati", "`frascati`", "Somestraat 1", "jazz", "DENIED", "VENUES",
                 "jazzin_amsterdam.py"):
        assert text in issue["body"]

    run_one(session, SLUG, tracker=gh, today=TODAY)           # nothing new
    assert issue["comments"] == []

    feed[:] = _bimhuis() + [("jazz", _item("Frascati", 1)), ("pop", _item("Felix Meritis", 2))]
    run_one(session, SLUG, tracker=gh, today=TODAY)
    assert list(gh.issues) == [1] and len(issue["comments"]) == 1
    assert "Felix Meritis" in issue["comments"][0] and "Frascati" not in issue["comments"][0]

    gh.close_issue(1)                                         # reviewed
    feed[:] += [("jazz", _item("De Groene Olifant", 3))]
    run_one(session, SLUG, tracker=gh, today=TODAY)
    assert list(gh.issues) == [1, 2] and gh.issues[2]["labels"] == [REVIEW_LABEL]


def test_review_without_github_is_logged(session, feed, caplog):
    feed[:] = _bimhuis() + [("jazz", _item("Frascati", 1))]
    with caplog.at_level(logging.WARNING):
        r = run_one(session, SLUG, today=TODAY)              # LoggingTracker
    assert r.ok and r.new_venues
    assert "would open issue 'jazzin-amsterdam: venues to review'" in caplog.text


def test_github_failure_on_review_never_fails_the_run(session, feed):
    class Boom(FakeTracker):
        def open_issue(self, title, body, labels):
            if labels == [REVIEW_LABEL]:
                raise RuntimeError("github down")
            return super().open_issue(title, body, labels)

    feed[:] = _bimhuis() + [("jazz", _item("Frascati", 1))]
    r = run_one(session, SLUG, tracker=Boom(), today=TODAY)
    assert r.ok and session.query(Venue).filter_by(slug="frascati").one()


def test_quiet_discovered_venue_is_not_degraded_and_its_events_age_out(session, feed):
    gh = FakeTracker()
    frascati = [("theater", _item("Frascati", 100 + i, days=4 + i)) for i in range(12)]
    for _ in range(4):                                        # baseline incl. frascati
        feed[:] = _bimhuis(40) + frascati
        assert run_one(session, SLUG, tracker=gh, today=TODAY).verdict == h.HEALTHY

    # Frascati gets denied (or merged) in code / vanishes from the feed: the
    # source stays healthy, and its upcoming events are hidden after 3 runs.
    # (Source coverage still counts them: a venue this size within a source
    # this small would rightly flag the source — see the 60% rule.)
    feed[:] = _bimhuis(40)
    for _ in range(3):
        r = run_one(session, SLUG, tracker=gh, today=TODAY)
        assert r.verdict == h.HEALTHY, r.fired
    v = session.query(Venue).filter_by(slug="frascati").one()
    assert v.events and all(e.hidden_at is not None for e in v.events)
    latest = session.query(ScrapeRun).order_by(ScrapeRun.id.desc()).first()
    assert "frascati" not in latest.metrics["venues"]
    # gh: only the one review issue (from the first run), no health issue
    assert [i["labels"] for i in gh.issues.values()] == [[REVIEW_LABEL]]


def test_ack_covers_discovered_venues(session, feed):
    gh = FakeTracker()
    feed[:] = _bimhuis() + [("theater", _item("Frascati", 1))]
    run_one(session, SLUG, tracker=gh, today=TODAY)
    feed[:] = _bimhuis()
    run_one(session, SLUG, tracker=gh, today=TODAY)
    health_ops.ack(session, SLUG, gh, today=TODAY)
    [ev] = session.query(Venue).filter_by(slug="frascati").one().events
    assert ev.hidden_at is not None


def test_review_table_escapes_pipes_in_names():
    from cartelera.discovery import render_review
    body = render_review(SLUG, "jazzin_amsterdam", [
        {"slug": "ita-internationaal-theater", "name": "ITA | Internationaal Theater",
         "address": None, "categories": ["theater"], "events": 8}], TODAY, first=True)
    row = next(l for l in body.splitlines() if "ita-internationaal-theater" in l)
    assert "ITA \\| Internationaal Theater" in row and row.count(" | ") == 4


def test_registry_holds_only_the_overrides():
    _scraper, source = REGISTRY[SLUG]
    assert {v.slug for v in source.venues} == {slug for slug, *_ in jazzin.VENUES}


# --- override venues gain categories from the feed (extends_venue_categories) -------

def test_override_venue_gains_category_membership_and_list_events(session, feed):
    from cartelera.queries import events_for_list
    # Bimhuis is a jazz-only override; jazzin now lists a gig in classical too.
    feed[:] = _bimhuis() + [("classical", _item("Bimhuis", 1, days=2, title="Bach"))]
    gh = FakeTracker()
    r = run_one(session, SLUG, tracker=gh, today=TODAY)
    assert r.ok and r.verdict == h.HEALTHY, r.fired

    v = session.query(Venue).filter_by(slug="bimhuis").one()
    assert {c.slug for c in v.categories} == {"jazz", "classical"}
    assert _memberships(session, v) == {("jazz", "jazz"), ("classical", "classical")}
    # listed right away, under the whitelist: only the classical event
    assert [e.title for e in events_for_list(session, "amsterdam", "classical", TODAY)] == ["Bach"]
    assert "Bach" not in {e.title for e in events_for_list(session, "amsterdam", "jazz", TODAY)}

    # reported: result, metrics, review issue
    assert r.new_venues == []
    assert r.new_categories == [{"slug": "bimhuis", "name": "Bimhuis",
                                 "category": "classical", "events": 1}]
    run = session.query(ScrapeRun).filter_by(source_slug=SLUG).one()
    assert run.metrics["new_categories"] == r.new_categories
    [issue] = gh.issues.values()
    assert issue["labels"] == [REVIEW_LABEL]
    assert "| Bimhuis | `bimhuis` | classical | 1 |" in issue["body"]
    assert "DENIED" not in issue["body"]  # no new venues: no venue instructions

    # nothing new next run: no report, no comment
    r = run_one(session, SLUG, tracker=gh, today=TODAY)
    assert r.new_categories == [] and issue["comments"] == []
    assert "new_categories" not in session.query(ScrapeRun).order_by(
        ScrapeRun.id.desc()).first().metrics

    # gone from the classical calendar: never removed
    feed[:] = _bimhuis()
    run_one(session, SLUG, tracker=gh, today=TODAY)
    assert _memberships(session, v) == {("jazz", "jazz"), ("classical", "classical")}

    # a further new category is a comment on the open issue
    feed[:] = _bimhuis() + [("pop", _item("Bimhuis", 2, days=2))]
    r = run_one(session, SLUG, tracker=gh, today=TODAY)
    assert [c["category"] for c in r.new_categories] == ["pop"]
    assert len(gh.issues) == 1 and len(issue["comments"]) == 1
    assert "`bimhuis` | pop" in issue["comments"][0]


def test_reseed_keeps_categories_and_memberships_a_run_added(session, feed):
    feed[:] = _bimhuis() + [("classical", _item("Bimhuis", 1, days=2))]
    run_one(session, SLUG, tracker=FakeTracker(), today=TODAY)
    seed(session)
    session.expire_all()
    v = session.query(Venue).filter_by(slug="bimhuis").one()
    assert {c.slug for c in v.categories} == {"jazz", "classical"}
    assert _memberships(session, v) == {("jazz", "jazz"), ("classical", "classical")}


def test_new_venue_and_new_category_in_one_run_share_one_issue(session, feed):
    feed[:] = _bimhuis() + [("pop", _item("Bimhuis", 1)), ("jazz", _item("Frascati", 2))]
    gh = FakeTracker()
    r = run_one(session, SLUG, tracker=gh, today=TODAY)
    assert [v["slug"] for v in r.new_venues] == ["frascati"]
    assert [(c["slug"], c["category"]) for c in r.new_categories] == [("bimhuis", "pop")]
    [issue] = gh.issues.values()
    assert "`frascati`" in issue["body"] and "`bimhuis` | pop" in issue["body"]
    assert "DENIED" in issue["body"]


def test_discovered_venue_growth_is_not_reported_as_a_new_category(session, feed):
    feed[:] = _bimhuis() + [("jazz", _item("Frascati", 1))]
    run_one(session, SLUG, tracker=FakeTracker(), today=TODAY)
    feed[:] += [("theater", _item("Frascati", 2))]
    r = run_one(session, SLUG, tracker=FakeTracker(), today=TODAY)
    assert r.new_categories == []
    v = session.query(Venue).filter_by(slug="frascati").one()
    assert {c.slug for c in v.categories} == {"jazz", "theater"}
