"""DB-level scraper-health tests: null guard, miss counting / hiding, the
run → verdict → write/hide → issue flow (fake scraper + fake GitHub), ack,
rekey, and that list queries exclude hidden events."""
from __future__ import annotations
import datetime as dt
import re
from pathlib import Path

import httpx
import pytest
from sqlalchemy import inspect

from cartelera import health as h
from cartelera import health_ops
from cartelera.migrate import apply_migrations
from cartelera.models import Event, EventTranslation, ScrapeRun, SourceHealth, Venue
from cartelera.queries import events_for_list
from cartelera.run import run_one
from cartelera.scrapers import REGISTRY
from cartelera.seed import seed
from cartelera.types import ScrapedEvent, ScrapedTranslation
from cartelera.upsert import count_misses, upsert_venue_events

TODAY = dt.date.today()


def _se(eid: str, days: int = 1, **kw) -> ScrapedEvent:
    base = dict(title=f"Show {eid}", start_date=TODAY + dt.timedelta(days=days),
                source_url=f"https://x/{eid}", category_slugs=["jazz"], external_id=eid)
    base.update(kw)
    return ScrapedEvent(**base)


class FakeScraper:
    venue_slug = "jamboree"

    def __init__(self):
        self.events: list[ScrapedEvent] = []
        self.exc: BaseException | None = None

    def scrape(self):
        if self.exc is not None:
            raise self.exc
        return list(self.events)


class FakeTracker:
    repo = "jpjagt/cartelita"

    def __init__(self):
        self.issues: dict[int, dict] = {}

    def open_issue(self, title, body, labels):
        n = len(self.issues) + 1
        self.issues[n] = {"title": title, "body": body, "labels": labels,
                          "state": "open", "comments": []}
        return n

    def comment(self, number, body):
        self.issues[number]["comments"].append(body)

    def update_issue(self, number, title, labels):
        self.issues[number].update(title=title, labels=labels)

    def close_issue(self, number):
        self.issues[number]["state"] = "closed"

    def is_open(self, number):
        return self.issues[number]["state"] == "open"


@pytest.fixture()
def fake(session, monkeypatch):
    seed(session)
    scraper = FakeScraper()
    monkeypatch.setitem(REGISTRY, "jamboree", (scraper, REGISTRY["jamboree"][1]))
    return scraper


def _events(session, **filters) -> dict[str, Event]:
    session.expire_all()
    return {e.external_id: e for e in session.query(Event).filter_by(**filters)}


# --- migration ---------------------------------------------------------------------

def test_migration_adds_health_tables_and_columns(engine):
    apply_migrations(engine)
    insp = inspect(engine)
    assert {"scrape_run", "source_health"} <= set(insp.get_table_names())
    cols = {c["name"] for c in insp.get_columns("event")}
    assert {"last_seen_at", "missed_runs", "hidden_at"} <= cols


# --- null guard ---------------------------------------------------------------------

def test_null_guard_never_blanks_known_values(session):
    seed(session)
    full = _se("1", price="12€", start_time=dt.time(21), start_times=[dt.time(21)],
               end_date=TODAY, end_time=dt.time(23), description="desc", image_url="https://i/",
               recurrence_hint="weekly", language="en", annotations=["bebop"])
    upsert_venue_events(session, "jamboree", [full])
    session.commit()
    upsert_venue_events(session, "jamboree", [_se("1", title="Renamed", price="")])
    session.commit()
    ev = _events(session)["1"]
    assert ev.title == "Renamed"  # values still change
    assert (ev.price, ev.start_time, ev.start_times, ev.end_date, ev.end_time) == (
        "12€", dt.time(21), [dt.time(21)], TODAY, dt.time(23))
    assert (ev.description, ev.image_url, ev.recurrence_hint, ev.language, ev.annotations) == (
        "desc", "https://i/", "weekly", "en", ["bebop"])
    upsert_venue_events(session, "jamboree", [_se("1", price="15€", start_time=dt.time(20))])
    session.commit()
    ev = _events(session)["1"]
    assert (ev.price, ev.start_time, ev.start_times) == ("15€", dt.time(20), [])


def test_null_guard_on_translations(session):
    seed(session)
    upsert_venue_events(session, "jamboree", [_se("t", translations=[
        ScrapedTranslation(lang="en", title="EN", description="en desc", source_url="https://en/")])])
    session.commit()
    # extra-language fetch failed: no translations at all → kept
    upsert_venue_events(session, "jamboree", [_se("t")])
    session.commit()
    # translation present but fields missing → stored fields kept
    upsert_venue_events(session, "jamboree", [_se("t", translations=[
        ScrapedTranslation(lang="en", title="EN 2")])])
    session.commit()
    session.expire_all()
    (tr,) = session.query(EventTranslation).all()
    assert (tr.title, tr.description, tr.source_url) == ("EN 2", "en desc", "https://en/")


# --- miss counting / hiding ---------------------------------------------------------

def test_misses_hide_after_three_and_reappearance_unhides(session):
    seed(session)
    venue = session.query(Venue).filter_by(slug="jamboree").one()
    past = _se("past", days=-3)
    upsert_venue_events(session, "jamboree", [_se("a"), _se("b"), past])
    session.commit()
    for i in range(1, 4):
        seen: set[int] = set()
        upsert_venue_events(session, "jamboree", [_se("a")], seen_ids=seen)
        missed, hidden = count_misses(session, venue.id, seen, TODAY)
        session.commit()
        assert (missed, hidden) == (1, 1 if i == 3 else 0)
        evs = _events(session)
        assert evs["b"].missed_runs == i and evs["a"].missed_runs == 0
    evs = _events(session)
    assert evs["b"].hidden_at is not None and evs["a"].hidden_at is None
    assert evs["past"].missed_runs == 0 and evs["past"].hidden_at is None  # never touched
    # hidden events are no longer counted
    assert count_misses(session, venue.id, {evs["a"].id}, TODAY) == (0, 0)
    # reappearance: visible again, counter reset
    upsert_venue_events(session, "jamboree", [_se("a"), _se("b")])
    session.commit()
    evs = _events(session)
    assert evs["b"].hidden_at is None and evs["b"].missed_runs == 0
    assert evs["b"].last_seen_at is not None


def test_list_queries_exclude_hidden_events(session):
    seed(session)
    upsert_venue_events(session, "jamboree", [_se("vis"), _se("gone")])
    session.commit()
    session.query(Event).filter_by(external_id="gone").update({"hidden_at": dt.datetime.now(dt.UTC)})
    session.commit()
    evs = events_for_list(session, "barcelona", "jazz", on_or_after=TODAY)
    assert [e.external_id for e in evs] == ["vis"]


def test_web_queries_filter_hidden_events():
    """Every event query in the web frontend must exclude hidden events."""
    src = (Path(__file__).parents[2] / "web/src/lib/queries.ts").read_text()
    joins = re.findall(r"JOIN event e ON[^\n]*", src)
    assert joins, "expected event queries in web/src/lib/queries.ts"
    assert all("e.hidden_at IS NULL" in j for j in joins), joins


# --- run → verdict → data ----------------------------------------------------------

def _run(session, tracker):
    return run_one(session, "jamboree", tracker=tracker, today=TODAY)


def _full(n=30):
    return [_se(f"e{i}", days=1 + 3 * i, price="10€", start_time=dt.time(21)) for i in range(n)]


def test_run_healthy_truncated_down_recovered(session, fake):
    gh = FakeTracker()
    fake.events = _full()
    for _ in range(3):  # build a baseline
        r = _run(session, gh)
        assert (r.ok, r.verdict) == (True, h.HEALTHY)
    assert session.query(Event).count() == 30

    # pagination dies after the first page: degraded, written, nothing missed
    fake.events = _full()[:12] + [_se("new1", days=2)]
    r = _run(session, gh)
    assert (r.ok, r.verdict) == (True, h.DEGRADED)
    assert any("re-saw" in f for f in r.fired)
    assert all(e.missed_runs == 0 and e.hidden_at is None for e in _events(session).values())
    assert "new1" in _events(session)
    assert gh.issues == {}  # one degraded run: no issue yet
    r = _run(session, gh)
    assert r.verdict == h.DEGRADED
    assert [i["title"] for i in gh.issues.values()] == ["scraper: jamboree — degraded"]
    assert gh.issues[1]["labels"] == ["scraper-health", "kind:degraded"]
    assert "coverage_drop" in gh.issues[1]["body"]

    # site down: nothing written, issue gets a comment (verdict changed)
    fake.exc = httpx.ConnectError("refused")
    r = _run(session, gh)
    assert (r.ok, r.verdict) == (False, h.SITE_DOWN)
    assert len(gh.issues[1]["comments"]) == 1
    assert all(e.missed_runs == 0 for e in _events(session).values())

    # recovered, with two events genuinely cancelled
    fake.exc = None
    fake.events = _full()[2:] + [_se("new1", days=2)]
    r = _run(session, gh)
    assert (r.ok, r.verdict) == (True, h.HEALTHY)
    assert gh.issues[1]["state"] == "closed" and "Recovered" in gh.issues[1]["comments"][-1]
    evs = _events(session)
    assert evs["e0"].missed_runs == 1 and evs["e1"].missed_runs == 1
    for _ in range(2):
        _run(session, gh)
    evs = _events(session)
    assert evs["e0"].hidden_at is not None and evs["e1"].hidden_at is not None
    assert evs["e2"].hidden_at is None

    runs = session.query(ScrapeRun).order_by(ScrapeRun.id).all()
    assert [r.verdict for r in runs] == ["healthy"] * 3 + ["degraded"] * 2 + [
        "site_down"] + ["healthy"] * 3
    assert runs[5].error_kind == "transport" and "ConnectError" in runs[5].error_message
    assert runs[3].metrics["source"]["known_upcoming"] == 30
    assert runs[3].metrics["source"]["reseen"] == 12
    assert runs[3].metrics["fired"]
    assert session.get(SourceHealth, "jamboree").issue_number is None


def test_broken_and_site_down_runs_keep_data_and_count_no_misses(session, fake):
    gh = FakeTracker()
    fake.events = [_se("a", price="5€"), _se("b")]
    _run(session, gh)
    # write-side failure (unknown category) → broken, rolled back
    fake.events = [_se("a", price="99€"), _se("x", category_slugs=["nope"])]
    r = _run(session, gh)
    assert (r.ok, r.verdict) == (False, h.BROKEN)
    assert "unknown category slug" in r.error
    evs = _events(session)
    assert set(evs) == {"a", "b"} and evs["a"].price == "5€"
    assert all(e.missed_runs == 0 for e in evs.values())
    fake.events, fake.exc = [], RuntimeError("selector gone")
    r = _run(session, gh)
    assert r.verdict == h.BROKEN
    assert [i["title"] for i in gh.issues.values()] == ["scraper: jamboree — broken"]
    assert "selector gone" in gh.issues[1]["body"]
    fake.exc = httpx.HTTPStatusError(
        "503", request=httpx.Request("GET", "https://x/"),
        response=httpx.Response(503, request=httpx.Request("GET", "https://x/")))
    assert _run(session, gh).verdict == h.SITE_DOWN
    assert all(e.missed_runs == 0 for e in _events(session).values())


def test_degraded_run_does_not_hide(session, fake):
    gh = FakeTracker()
    fake.events = _full(20)
    _run(session, gh)
    fake.events = _full(20)[:5]  # coverage 5/20 → degraded even on cold start
    for _ in range(4):
        assert _run(session, gh).verdict == h.DEGRADED
    assert all(e.hidden_at is None and e.missed_runs == 0 for e in _events(session).values())


# --- issue sync / ack ----------------------------------------------------------------

def _record(session, verdict, kind=None, when=None):
    session.add(ScrapeRun(source_slug="jamboree", verdict=verdict, error_kind=kind,
                          started_at=when or dt.datetime.now(dt.UTC)))
    session.commit()


def test_sync_weekly_cap_and_closed_by_hand(session, fake):
    gh = FakeTracker()
    t0 = dt.datetime(2026, 10, 1, 2, tzinfo=dt.UTC)
    for d in range(2):
        _record(session, "broken", "exception", t0 + dt.timedelta(days=d))
        health_ops.sync_issue(session, "jamboree", gh, now=t0 + dt.timedelta(days=d))
    assert len(gh.issues) == 1
    for d in range(2, 8):  # same failure, under a week since the last comment
        _record(session, "broken", "exception", t0 + dt.timedelta(days=d))
        health_ops.sync_issue(session, "jamboree", gh, now=t0 + dt.timedelta(days=d))
    assert gh.issues[1]["comments"] == []
    _record(session, "broken", "exception", t0 + dt.timedelta(days=8))
    health_ops.sync_issue(session, "jamboree", gh, now=t0 + dt.timedelta(days=8))
    assert len(gh.issues[1]["comments"]) == 1 and "weekly" in gh.issues[1]["comments"][0]
    # the owner closes it by hand while it is still broken: a fresh issue opens
    gh.close_issue(1)
    _record(session, "broken", "exception", t0 + dt.timedelta(days=9))
    health_ops.sync_issue(session, "jamboree", gh, now=t0 + dt.timedelta(days=9))
    assert len(gh.issues) == 2 and gh.issues[2]["state"] == "open"


def test_ack_closes_issue_resets_streak_and_joins_baseline(session, fake):
    gh = FakeTracker()
    fake.events = [_se(f"s{i}") for i in range(4)]
    for _ in range(2):
        _record(session, "degraded")
        health_ops.sync_issue(session, "jamboree", gh)
    assert gh.issues[1]["state"] == "open"
    msg = health_ops.ack(session, "jamboree", gh)
    assert "closed issue #1" in msg
    assert gh.issues[1]["state"] == "closed" and "Acknowledged" in gh.issues[1]["comments"][-1]
    sh = session.get(SourceHealth, "jamboree")
    assert sh.issue_number is None
    latest = session.query(ScrapeRun).order_by(ScrapeRun.id.desc()).first()
    assert latest.acked
    # the streak restarts: one more degraded run does not reopen
    _record(session, "degraded")
    health_ops.sync_issue(session, "jamboree", gh)
    assert len(gh.issues) == 1
    assert any("jamboree" in line and "degraded" in line
               for line in health_ops.status_lines(session))


def test_github_failure_never_fails_the_run(session, fake):
    class Exploding(FakeTracker):
        def open_issue(self, *a):
            raise httpx.ConnectError("github down")
    fake.exc = RuntimeError("boom")
    gh = Exploding()
    _run(session, gh)
    r = _run(session, gh)
    assert r.verdict == h.BROKEN and session.query(ScrapeRun).count() == 2


# --- rekey (jazzin legacy ids) ----------------------------------------------------------

def test_rekey_hides_legacy_numeric_rows_and_acks(session, monkeypatch):
    seed(session)
    source = REGISTRY["jazzin-amsterdam"][1]
    scraper = FakeScraper()
    monkeypatch.setitem(REGISTRY, "jazzin-amsterdam", (scraper, source))
    gh = FakeTracker()
    legacy = [_se(str(1000 + i), venue_slug="bimhuis") for i in range(12)]
    upsert_venue_events(session, "bimhuis", legacy + [_se("999", days=-5)])
    session.commit()
    with pytest.raises(ValueError, match="must have succeeded"):
        health_ops.rekey(session, "jazzin-amsterdam", gh, apply=False, today=TODAY)
    scraper.events = [_se(f"k{i:015d}", title=f"Show {1000 + i}", venue_slug="bimhuis")
                      for i in range(12)]
    r = run_one(session, "jazzin-amsterdam", tracker=gh, today=TODAY)
    assert r.verdict == h.DEGRADED  # every legacy row "missing": coverage 0
    out = health_ops.rekey(session, "jazzin-amsterdam", gh, apply=False, today=TODAY)
    assert "would hide 12" in out
    assert _events(session, hidden_at=None).keys() >= {"1000", "k000000000000000"}
    out = health_ops.rekey(session, "jazzin-amsterdam", gh, apply=True, today=TODAY)
    assert "hid 12" in out
    evs = _events(session)
    assert all(evs[str(1000 + i)].hidden_at is not None for i in range(12))
    assert evs["999"].hidden_at is None  # past: untouched
    assert all(evs[f"k{i:015d}"].hidden_at is None for i in range(12))
    assert session.query(ScrapeRun).filter_by(source_slug="jazzin-amsterdam").one().acked
    # next run is healthy: the legacy rows are no longer known
    assert run_one(session, "jazzin-amsterdam", tracker=gh, today=TODAY).verdict == h.HEALTHY
    with pytest.raises(ValueError, match="supports"):
        health_ops.rekey(session, "jamboree", gh, apply=False)


def test_health_cli_dispatch(session, fake, capsys):
    gh = FakeTracker()
    assert health_ops.main(session, [], gh) == 0
    assert "jamboree" in capsys.readouterr().out
    assert health_ops.main(session, ["ack", "jamboree"], gh) == 1  # no runs yet
    assert "no recorded runs" in capsys.readouterr().err
    assert health_ops.main(session, ["rekey", "jazzin-amsterdam", "--force"], gh) == 1
    assert "usage" in capsys.readouterr().err
    assert health_ops.main(session, ["bogus"], gh) == 1
