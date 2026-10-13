"""Venue-scoped verdicts for multi-venue sources (scraper-health spec, revision
2026-10-13), end to end through run_one with the real jazzin.amsterdam scraper
(its fetch stubbed): a venue-level rule degrades only that venue, its events
are neither missed nor hidden while the rest of the source proceeds, its
baseline / coverage reference skip runs that degraded it, long-degraded venues
go to the review issue (never a source issue), and `health ack <source>
<venue>` / `health <source>`."""
from __future__ import annotations
import datetime as dt

import pytest

from cartelera import health as h
from cartelera import health_ops
from cartelera.discovery import REVIEW_LABEL
from cartelera.models import Event, ScrapeRun, SourceHealth, Venue
from cartelera.run import run_one
from cartelera.scrapers import jazzin_amsterdam as jazzin
from cartelera.seed import seed

from tests.test_health_db import FakeTracker, _events

TODAY = dt.date.today()
SLUG = jazzin.SOURCE_SLUG


def _item(venue: str, id_: int, days: int) -> dict:
    return {"id": id_, "venue": venue, "title": f"Gig {id_}",
            "date": (TODAY + dt.timedelta(days=days)).isoformat(), "time": "20:30:00",
            "price": "€10", "site": f"https://example.org/{id_}",
            "address": "Somestraat 1, 1011 AA Amsterdam", "source": "submit"}


def _bimhuis(skip: int = 0) -> list[tuple[str, dict]]:
    return [("jazz", _item("Bimhuis", 1000 + i, days=3 + i)) for i in range(skip, 40)]


def _mezrab(n: int = 15) -> list[tuple[str, dict]]:
    return [("theater", _item("Mezrab", 2000 + i, days=2 + 2 * i)) for i in range(n)]


@pytest.fixture()
def feed(session, monkeypatch):
    seed(session)
    items: list[tuple[str, dict]] = []
    monkeypatch.setattr(jazzin, "fetch_items", lambda: list(items))
    return items


def _run(session, gh):
    return run_one(session, SLUG, tracker=gh, today=TODAY)


def _venue_events(session, slug) -> list[Event]:
    session.expire_all()
    v = session.query(Venue).filter_by(slug=slug).one()
    return session.query(Event).filter_by(venue_id=v.id).all()


def _baseline(session, feed, gh, runs: int = 4):
    feed[:] = _bimhuis() + _mezrab()
    for _ in range(runs):
        assert _run(session, gh).verdict == h.HEALTHY


def _health_issues(gh):
    return [i for i in gh.issues.values() if "scraper-health" in i["labels"]]


def _review_issues(gh):
    return [i for i in gh.issues.values() if i["labels"] == [REVIEW_LABEL]]


def test_empty_venue_degrades_only_that_venue(session, feed):
    gh = FakeTracker()
    _baseline(session, feed, gh)
    # Mezrab vanishes upstream; two Bimhuis gigs are genuinely cancelled.
    feed[:] = _bimhuis(skip=2)
    for i in range(3):
        r = _run(session, gh)
        assert (r.ok, r.verdict) == (True, h.HEALTHY), r.fired
        assert r.degraded_venues == ["mezrab"]
        assert any(f.startswith("venue:mezrab: ") for f in r.fired)

    latest = session.query(ScrapeRun).order_by(ScrapeRun.id.desc()).first()
    assert latest.verdict == h.HEALTHY
    assert latest.metrics["degraded_venues"] == ["mezrab"]
    assert latest.metrics["venues"]["mezrab"]["verdict"] == h.DEGRADED
    assert latest.metrics["venues"]["bimhuis"]["verdict"] == h.HEALTHY
    assert {f["rule"] for f in latest.metrics["fired"]} >= {"empty", "coverage_drop"}
    assert all(f["scope"] == "venue:mezrab" for f in latest.metrics["fired"])

    # the healthy venue's misses are counted and hidden...
    evs = _events(session)
    assert evs[jazzin_key(session, "bimhuis", "Gig 1000")].hidden_at is not None
    assert evs[jazzin_key(session, "bimhuis", "Gig 1002")].hidden_at is None
    # ...the degraded venue's events are untouched
    mez = _venue_events(session, "mezrab")
    assert len(mez) == 15 and all(e.missed_runs == 0 and e.hidden_at is None for e in mez)
    assert _health_issues(gh) == []


def jazzin_key(session, venue_slug, title) -> str:
    return next(e.external_id for e in _venue_events(session, venue_slug) if e.title == title)


def test_degraded_venue_does_not_poison_its_own_baseline(session, feed):
    gh = FakeTracker()
    _baseline(session, feed, gh)
    feed[:] = _bimhuis()
    # well past BASELINE_WINDOW healthy source runs: had those runs fed
    # Mezrab's 0s into its baseline, the median would be 0 and it would score
    # healthy — and its events would be missed and hidden.
    for _ in range(h.BASELINE_WINDOW + 2):
        r = _run(session, gh)
        assert r.verdict == h.HEALTHY and r.degraded_venues == ["mezrab"]
    assert all(e.hidden_at is None and e.missed_runs == 0
               for e in _venue_events(session, "mezrab"))


def test_coverage_reference_of_a_degraded_venue_is_its_last_trusted_run(session, feed):
    gh = FakeTracker()
    _baseline(session, feed, gh)
    feed[:] = _bimhuis() + _mezrab(5)  # Mezrab truncated to 5 of 15
    for _ in range(3):  # stays degraded: measured against the 15, not its own 5
        r = _run(session, gh)
        assert r.verdict == h.HEALTHY and r.degraded_venues == ["mezrab"], r.fired
        m = session.query(ScrapeRun).order_by(ScrapeRun.id.desc()).first().metrics
        assert (m["venues"]["mezrab"]["known_upcoming"], m["venues"]["mezrab"]["reseen"]) == (15, 5)
        # a healthy venue's reference is simply the previous run
        assert m["venues"]["bimhuis"]["known_upcoming"] == 40
    feed[:] = _bimhuis() + _mezrab()
    assert _run(session, gh).degraded_venues == []


def test_long_degraded_venue_goes_to_the_review_issue_not_a_source_issue(session, feed):
    gh = FakeTracker()
    _baseline(session, feed, gh)
    feed[:] = _bimhuis()
    for _ in range(h.VENUE_REVIEW_STREAK - 1):
        _run(session, gh)
    assert gh.issues == {}
    _run(session, gh)
    assert _health_issues(gh) == []
    [review] = _review_issues(gh)
    assert review["title"] == f"{SLUG}: venues to review"
    for text in ("Mezrab", "`mezrab`", "| 7 |", "empty", f"cartelera health ack {SLUG} <slug>"):
        assert text in review["body"], text
    # unchanged: no comment (weekly cap), still no source issue
    _run(session, gh)
    assert review["comments"] == [] and _health_issues(gh) == []
    sh = session.get(SourceHealth, SLUG)
    assert sh.venue_review_signature.startswith("mezrab:") and sh.venue_review_comment_at

    # weekly reminder
    sh.venue_review_comment_at -= h.COMMENT_INTERVAL
    session.commit()
    _run(session, gh)
    assert len(review["comments"]) == 1 and "weekly" in review["comments"][0]

    # acked → next run posts "cleared" once
    health_ops.ack_venue(session, SLUG, "mezrab", today=TODAY)
    r = _run(session, gh)
    assert r.degraded_venues == []
    assert len(review["comments"]) == 2 and "any more" in review["comments"][1]
    _run(session, gh)
    assert len(review["comments"]) == 2
    assert session.get(SourceHealth, SLUG).venue_review_signature is None


def test_source_issue_opened_for_venue_rules_closes_on_next_source_healthy_run(session, feed):
    """The prod situation: before venue-scoped verdicts a venue rule degraded
    the whole source and opened `#1 (degraded)`."""
    gh = FakeTracker()
    _baseline(session, feed, gh)
    old_style = {"source": {"emitted": 40}, "venues": {}, "fired": [
        {"scope": "venue:mezrab", "rule": "empty", "value": 0, "reference": 15, "detail": "0 events"}]}
    for _ in range(2):
        session.add(ScrapeRun(source_slug=SLUG, verdict="degraded", metrics=old_style,
                              started_at=dt.datetime.now(dt.UTC)))
        session.commit()
        health_ops.sync_issue(session, SLUG, gh)
    [issue] = _health_issues(gh)
    assert issue["state"] == "open" and issue["title"] == f"scraper: {SLUG} — degraded"

    feed[:] = _bimhuis()
    r = _run(session, gh)
    assert r.verdict == h.HEALTHY and r.degraded_venues == ["mezrab"]
    assert issue["state"] == "closed"
    assert "Recovered" in issue["comments"][-1]
    assert "1 venue(s) are still degraded" in issue["comments"][-1]
    assert session.get(SourceHealth, SLUG).issue_number is None
    # the old-style degraded runs were never a reference for Mezrab: it is
    # still measured against the healthy baseline runs
    assert all(e.hidden_at is None for e in _venue_events(session, "mezrab"))


def test_source_level_rule_still_degrades_the_whole_source(session, feed):
    gh = FakeTracker()
    _baseline(session, feed, gh)
    feed[:] = _bimhuis()[:10] + _mezrab()  # aggregate coverage 25/55 → source rule
    r = _run(session, gh)
    assert r.verdict == h.DEGRADED
    assert "bimhuis" in r.degraded_venues
    assert all(e.missed_runs == 0 for e in _events(session).values())


def test_venue_ack_hides_unseen_and_restarts_its_baseline(session, feed):
    gh = FakeTracker()
    _baseline(session, feed, gh)
    feed[:] = _bimhuis() + _mezrab(4)  # programme shrinks for good
    assert _run(session, gh).degraded_venues == ["mezrab"]
    msg = health_ops.ack_venue(session, SLUG, "mezrab", today=TODAY)
    assert "acked venue mezrab" in msg and "hid 11" in msg
    latest = session.query(ScrapeRun).order_by(ScrapeRun.id.desc()).first()
    assert latest.metrics["acked_venues"] == ["mezrab"] and not latest.acked
    mez = _venue_events(session, "mezrab")
    assert sum(e.hidden_at is not None for e in mez) == 11
    assert all(e.hidden_at is None for e in _venue_events(session, "bimhuis"))
    # the acked state is the new normal from now on
    for _ in range(4):
        r = _run(session, gh)
        assert r.verdict == h.HEALTHY and r.degraded_venues == [], r.fired
    # errors
    with pytest.raises(ValueError, match="not a venue of"):
        health_ops.ack_venue(session, SLUG, "jamboree")
    with pytest.raises(ValueError, match="single venue"):
        health_ops.ack_venue(session, "jamboree", "jamboree")


def test_health_overview_and_detail(session, feed, capsys):
    gh = FakeTracker()
    _baseline(session, feed, gh)
    feed[:] = _bimhuis()
    for _ in range(3):
        _run(session, gh)
    assert health_ops.main(session, [], gh) == 0
    out = capsys.readouterr().out
    line = next(l for l in out.splitlines() if l.startswith(SLUG))
    assert line.split()[1:4] == ["healthy", "0", "1"]

    assert health_ops.main(session, [SLUG], gh) == 0
    out = capsys.readouterr().out
    assert "degraded venues: 1" in out
    assert "mezrab" in out and "Mezrab" in out and "3 runs" in out
    assert "empty: 0 events" in out and "coverage_drop" in out
    assert f"cartelera health ack {SLUG} <venue>" in out

    assert health_ops.main(session, ["ack", SLUG, "mezrab"], gh) == 0
    assert "acked venue mezrab" in capsys.readouterr().out
    health_ops.main(session, [], gh)
    line = next(l for l in capsys.readouterr().out.splitlines() if l.startswith(SLUG))
    assert line.split()[3] == "-"
    health_ops.main(session, [SLUG], gh)
    assert "degraded venues: none" in capsys.readouterr().out
    assert health_ops.main(session, ["nope-source"], gh) == 1
    assert "unknown source" in capsys.readouterr().err
    assert health_ops.main(session, ["jamboree"], gh) == 0
    assert "never run" in capsys.readouterr().out
