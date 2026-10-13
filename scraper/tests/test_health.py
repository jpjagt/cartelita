"""Pure unit tests for cartelera.health: classification, metrics, baseline,
degraded rules, and the streak → issue state machine."""
from __future__ import annotations
import datetime as dt

import httpx
import pytest

from cartelera import health as h
from cartelera.health import ScopeMetrics as M
from cartelera.types import ScrapedEvent

TODAY = dt.date(2026, 10, 12)
NOW = dt.datetime(2026, 10, 12, 2, 0, tzinfo=dt.timezone.utc)


# --- classification ----------------------------------------------------------

def _status_error(code: int) -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "https://venue.example/agenda")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(code, request=req))


@pytest.mark.parametrize("exc,expected", [
    (httpx.ConnectError("refused"), (h.SITE_DOWN, h.ERR_TRANSPORT)),
    (httpx.ReadTimeout("slow"), (h.SITE_DOWN, h.ERR_TRANSPORT)),
    (httpx.RemoteProtocolError("eof"), (h.SITE_DOWN, h.ERR_TRANSPORT)),
    (_status_error(500), (h.SITE_DOWN, h.ERR_HTTP_5XX)),
    (_status_error(503), (h.SITE_DOWN, h.ERR_HTTP_5XX)),
    (_status_error(403), (h.SITE_DOWN, h.ERR_BLOCKED)),
    (_status_error(429), (h.SITE_DOWN, h.ERR_BLOCKED)),
    (_status_error(404), (h.BROKEN, h.ERR_HTTP_GONE)),
    (_status_error(410), (h.BROKEN, h.ERR_HTTP_GONE)),
    (_status_error(400), (h.BROKEN, h.ERR_HTTP_4XX)),
    (ValueError("unknown category slug 'x'"), (h.BROKEN, h.ERR_EXCEPTION)),
    (KeyError("price"), (h.BROKEN, h.ERR_EXCEPTION)),
])
def test_classify_exception(exc, expected):
    assert h.classify_exception(exc) == expected


def test_classify_walks_the_exception_chain():
    try:
        try:
            raise httpx.ConnectTimeout("dns")
        except httpx.ConnectTimeout as inner:
            raise RuntimeError("could not load listing") from inner
    except RuntimeError as outer:
        assert h.classify_exception(outer) == (h.SITE_DOWN, h.ERR_TRANSPORT)
    try:
        try:
            raise _status_error(429)
        except httpx.HTTPStatusError:
            raise ValueError("parse failed")  # implicit __context__
    except ValueError as outer:
        assert h.classify_exception(outer) == (h.SITE_DOWN, h.ERR_BLOCKED)


def test_error_tail_truncates_to_the_end():
    try:
        raise ValueError("x" * 10_000 + "THE-END")
    except ValueError as exc:
        tail = h.error_tail(exc, limit=200)
    assert len(tail) <= 201 and tail.rstrip().endswith("THE-END")


# --- metrics -------------------------------------------------------------------

def _ev(days: int, price=None, time=None, desc=None) -> ScrapedEvent:
    return ScrapedEvent(title="x", start_date=TODAY + dt.timedelta(days=days),
                        source_url="https://x/", category_slugs=["jazz"],
                        price=price, start_time=time, description=desc)


def test_compute_metrics():
    evs = [_ev(1, price="5€", time=dt.time(20)), _ev(30, desc="d"),
           ScrapedEvent(title="y", start_date=TODAY, source_url="u", category_slugs=["jazz"],
                        start_times=[dt.time(19)])]
    m = h.compute_metrics(evs, known_upcoming=10, reseen=7, today=TODAY)
    assert (m.emitted, m.horizon_days, m.coverage) == (3, 30, 0.7)
    assert m.fill == pytest.approx({"price": 1 / 3, "start_time": 2 / 3, "description": 1 / 3})
    empty = h.compute_metrics([], 4, 0, TODAY)
    assert empty.horizon_days is None and empty.fill == {} and empty.coverage == 0
    assert h.compute_metrics([], 0, 0, TODAY).coverage is None


def test_aggregate_metrics_weights_fill_by_emitted():
    a = M(10, 10, 9, 60, {"price": 1.0, "start_time": 1.0, "description": 0.0})
    b = M(30, 20, 20, 90, {"price": 0.0, "start_time": 1.0, "description": 1.0})
    s = h.aggregate_metrics([a, b, M(0, 3, 0, None, {})])
    assert (s.emitted, s.known_upcoming, s.reseen, s.horizon_days) == (40, 33, 29, 90)
    assert s.fill == pytest.approx({"price": 0.25, "start_time": 1.0, "description": 0.75})


def test_metrics_json_round_trip():
    m = M(5, 4, 3, 20, {"price": 0.5})
    assert M.from_json(m.to_json()).to_json() == m.to_json()


# --- baseline + rules ------------------------------------------------------------

FULL = {"price": 0.9, "start_time": 1.0, "description": 0.8}


def _hist(n, emitted=100, horizon=120, fill=FULL):
    return [M(emitted, emitted, emitted, horizon, dict(fill)) for _ in range(n)]


def _rules(m, hist, **kw):
    return [r.rule for r in h.evaluate_rules("source", m, h.compute_baseline(hist), **kw)]


def test_baseline_needs_three_runs_and_uses_medians():
    assert h.compute_baseline(_hist(2)) is None
    hist = [M(10, 0, 0, 30, {"price": 0.2}), M(100, 0, 0, 90, {"price": 0.9}),
            M(50, 0, 0, None, {"price": 0.5})]
    b = h.compute_baseline(hist)
    assert (b.runs, b.emitted, b.horizon_days, b.fill["price"]) == (3, 50, 60, 0.5)


def test_baseline_window_is_limited():
    hist = _hist(14, emitted=100) + _hist(10, emitted=1)
    assert h.compute_baseline(hist).emitted == 100


def test_healthy_run_fires_nothing():
    assert _rules(M(98, 100, 95, 118, dict(FULL)), _hist(5)) == []


def test_cold_start_skips_baseline_rules():
    # emitted 0, tiny horizon, no fields: nothing fires without 3 baseline runs
    assert _rules(M(0, 0, 0, None, {}), _hist(2)) == []
    assert _rules(M(5, 0, 0, 3, {"price": 0.0, "start_time": 0.0, "description": 0.0}),
                  []) == []


def test_coverage_rule_applies_even_on_cold_start():
    assert _rules(M(100, 100, 40, 120, dict(FULL)), []) == ["coverage_drop"]


def test_empty_rule_and_floor():
    assert _rules(M(0, 0, 0, None, {}), _hist(5, emitted=3)) == ["empty"]
    assert _rules(M(0, 0, 0, None, {}), _hist(5, emitted=2)) == []


def test_count_drop_rule_and_floor():
    assert _rules(M(49, 0, 0, 120, dict(FULL)), _hist(5)) == ["count_drop"]
    assert _rules(M(50, 0, 0, 120, dict(FULL)), _hist(5)) == []
    # baseline emitted below 10: skipped
    assert _rules(M(2, 0, 0, 120, dict(FULL)), _hist(5, emitted=9)) == []


def test_coverage_rule_and_floor():
    assert _rules(M(100, 20, 11, 120, dict(FULL)), _hist(5)) == ["coverage_drop"]
    assert _rules(M(100, 20, 12, 120, dict(FULL)), _hist(5)) == []
    # fewer than 10 known upcoming events: skipped
    assert _rules(M(100, 9, 0, 120, dict(FULL)), _hist(5)) == []


def test_horizon_rule_and_floor():
    assert _rules(M(100, 0, 0, 59, dict(FULL)), _hist(5)) == ["horizon_shrink"]
    assert _rules(M(100, 0, 0, 60, dict(FULL)), _hist(5)) == []
    assert _rules(M(100, 0, 0, 1, dict(FULL)), _hist(5, horizon=13)) == []


def test_field_drop_rule_and_floor():
    m = M(100, 0, 0, 120, {"price": 0.5, "start_time": 1.0, "description": 0.8})
    assert _rules(m, _hist(5)) == ["field_drop:price"]
    m = M(100, 0, 0, 120, {"price": 0.61, "start_time": 1.0, "description": 0.8})
    assert _rules(m, _hist(5)) == []
    low = {"price": 0.45, "start_time": 1.0, "description": 0.8}
    m = M(100, 0, 0, 120, {"price": 0.0, "start_time": 1.0, "description": 0.8})
    assert _rules(m, _hist(5, fill=low)) == []


def test_small_venue_guard_skips_ratio_rules():
    m = M(5, 0, 0, 2, {"price": 0.0, "start_time": 1.0, "description": 0.0})
    assert _rules(m, _hist(5, emitted=8), small_scope_guard=True) == []
    assert set(_rules(m, _hist(5, emitted=8))) == {"horizon_shrink", "field_drop:price",
                                                     "field_drop:description"}


def test_per_venue_evaluation_for_multi_venue_sources():
    big = {"a": _hist(5), "b": _hist(5)}
    good = M(100, 100, 100, 120, dict(FULL))
    # venue b collapses; the aggregate count is still above half the baseline
    run = h.RunMetrics(
        source=h.aggregate_metrics([good, M(10, 100, 10, 120, dict(FULL))]),
        venues={"a": good, "b": M(10, 100, 10, 120, dict(FULL))})
    fired = h.evaluate_run(run, _hist(5, emitted=200), big)
    scopes = {(r.scope, r.rule) for r in fired}
    assert ("venue:b", "count_drop") in scopes and ("venue:b", "coverage_drop") in scopes
    assert not any(s == "venue:a" for s, _ in scopes)
    # the aggregate's coverage (110/200) fires too: that degrades the source
    assert ("source", "coverage_drop") in scopes
    assert h.verdict_for(fired) == h.DEGRADED
    assert set(h.venue_rules(fired)) == {"b"}
    # a venue with too little history is skipped (only its coverage rule applies)
    run2 = h.RunMetrics(source=good, venues={"a": good, "new": M(0, 0, 0, None, {})})
    assert h.evaluate_run(run2, _hist(5), {"a": _hist(5)}) == []


def test_venue_level_rules_alone_leave_the_source_healthy():
    hist = {s: _hist(5) for s in "abcdefghij"}
    good = M(100, 100, 100, 120, dict(FULL))
    venues = {s: good for s in "abcdefghi"} | {"j": M(0, 100, 0, None, {})}
    run = h.RunMetrics(source=h.aggregate_metrics(venues.values()), venues=venues)
    fired = h.evaluate_run(run, _hist(5, emitted=1000), hist)
    assert {r.scope for r in fired} == {"venue:j"}
    assert h.verdict_for(fired) == h.HEALTHY
    assert {s: [r.rule for r in rs] for s, rs in h.venue_rules(fired).items()} == {
        "j": ["coverage_drop", "empty"]}
    j = run.to_json(fired)
    assert j["degraded_venues"] == ["j"]
    assert j["venues"]["j"]["verdict"] == h.DEGRADED and j["venues"]["a"]["verdict"] == h.HEALTHY


def test_single_venue_source_evaluated_once():
    m = M(0, 0, 0, None, {})
    run = h.RunMetrics(source=m, venues={"only": m})
    fired = h.evaluate_run(run, _hist(5), {"only": _hist(5)})
    assert [(r.scope, r.rule) for r in fired] == [("source", "empty")]


def test_truncated_pagination_is_caught_by_coverage_even_with_plausible_count():
    # page 2+ dies; the remaining page happens to hold new events → count
    # looks fine (60/100 > 0.5) but most known events are not re-seen.
    m = M(60, 100, 45, 110, dict(FULL))
    assert _rules(m, _hist(5)) == ["coverage_drop"]


def test_a_few_cancellations_stay_healthy():
    assert _rules(M(97, 100, 97, 120, dict(FULL)), _hist(5)) == []


# --- venue-scoped trust ---------------------------------------------------------

T0 = dt.datetime(2026, 10, 1, 2, tzinfo=dt.UTC)


def _run_view(i, verdict="healthy", venues=("a", "b"), degraded=(), acked=False,
              acked_venues=None, emitted=10):
    """Run i days after T0 (callers pass newest first)."""
    metrics = {"source": M(emitted * len(venues), 0, 0, 30).to_json(),
               "venues": {v: M(0 if v in degraded else emitted, 0, 0, 30).to_json()
                          for v in venues},
               "fired": [{"scope": f"venue:{v}", "rule": "empty", "detail": ""}
                         for v in degraded]}
    if acked_venues:
        metrics["acked_venues"] = list(acked_venues)
    return h.RunView(verdict, acked, None if verdict in ("broken", "site_down") else metrics,
                     T0 + dt.timedelta(days=i))


def test_venue_history_skips_runs_that_degraded_that_venue():
    runs = [_run_view(5, degraded=["b"]), _run_view(4, degraded=["b"]), _run_view(3),
            _run_view(2, "degraded"), _run_view(1, "broken"), _run_view(0)]
    assert [m.emitted for m in h.venue_history(runs, "a")] == [10, 10, 10, 10]
    assert [m.emitted for m in h.venue_history(runs, "b")] == [10, 10]
    # the source's own baseline ignores venue-level degradation
    assert len(h.source_history(runs)) == 4
    # a source-acked run counts for every venue, degraded or not
    acked = [_run_view(6, "degraded", degraded=["b"], acked=True)] + runs
    assert h.venue_history(acked, "b")[0].emitted == 0


def test_venue_ack_restarts_the_venue_baseline():
    runs = [_run_view(3), _run_view(2, degraded=["b"], acked_venues=["b"]), _run_view(1),
            _run_view(0)]
    assert [m.emitted for m in h.venue_history(runs, "b")] == [10, 0]
    assert len(h.venue_history(runs, "a")) == 4
    # even in a run whose source verdict was degraded
    runs = [_run_view(1, "degraded", degraded=["b"], acked_venues=["b"]), _run_view(0)]
    assert [m.emitted for m in h.venue_history(runs, "b")] == [0]
    assert len(h.venue_history(runs, "a")) == 1  # the healthy run 0 only


def test_source_ack_restarts_the_source_and_venue_baselines():
    runs = [_run_view(4), _run_view(3), _run_view(2, "degraded", degraded=["b"], acked=True),
            _run_view(1), _run_view(0)]
    assert len(h.source_history(runs)) == 3          # runs 4, 3 and the acked 2
    assert len(h.venue_history(runs, "a")) == 3
    assert [m.emitted for m in h.venue_history(runs, "b")] == [10, 10, 0]
    # an acked broken run wrote nothing: it is no new normal, history goes on
    broken = [_run_view(4), _run_view(3, "broken", acked=True), _run_view(1), _run_view(0)]
    assert len(h.source_history(broken)) == 3


def test_venue_reference_falls_back_to_its_last_trusted_run():
    runs = [_run_view(3, degraded=["b"]), _run_view(2, "broken"), _run_view(1, "degraded"),
            _run_view(0)]
    assert h.venue_reference(runs, "a") == T0 + dt.timedelta(days=3)
    assert h.venue_reference(runs, "b") == T0
    # a venue absent from the run (quiet / new) isn't degraded in it
    assert h.venue_reference(runs, "zzz") == T0 + dt.timedelta(days=3)
    assert h.venue_reference([_run_view(0, "degraded")], "a") is None


def test_venue_streak():
    runs = [_run_view(4, degraded=["b"]), _run_view(3, "site_down"),
            _run_view(2, "degraded", degraded=["b"]), _run_view(1, degraded=["b"]),
            _run_view(0)]
    assert h.venue_streak(runs, "b") == 3       # broken/site_down neither count nor break
    assert h.venue_streak(runs, "a") == 0
    acked = [_run_view(5, degraded=["b"]), _run_view(4, degraded=["b"], acked_venues=["b"])]
    assert h.venue_streak(acked + runs, "b") == 1
    assert h.venue_streak([_run_view(5, degraded=["b"], acked=True)] + runs, "b") == 0


def test_plan_venue_review():
    sig = h.venue_review_signature({"b": ["empty", "coverage_drop"], "a": ["horizon_shrink"]})
    assert sig == "a:horizon_shrink;b:coverage_drop,empty"
    assert h.venue_review_signature({}) is None
    assert h.plan_venue_review(None, None, None, NOW) is None
    assert h.plan_venue_review(sig, None, None, NOW) == "update"
    assert h.plan_venue_review(sig, sig, NOW - dt.timedelta(days=6), NOW) is None
    assert h.plan_venue_review(sig, sig, NOW - dt.timedelta(days=7), NOW) == "weekly"
    assert h.plan_venue_review("a:empty", sig, NOW, NOW) == "update"
    assert h.plan_venue_review(None, sig, NOW, NOW) == "cleared"


# --- streaks → issues --------------------------------------------------------------

def R(verdict, kind=None, rules=(), acked=False):
    return h.RunSummary(verdict, kind, list(rules), acked)


def _plan(runs, state=None, now=NOW):
    return h.plan_issue_actions("src", runs, state or h.IssueState(), now)


def test_streak_thresholds_open_issues():
    assert _plan([R("broken")])[0] == []
    acts, st = _plan([R("broken"), R("broken")])
    assert [type(a) for a in acts] == [h.OpenIssue] and acts[0].kind == "broken"
    assert acts[0].title == "scraper: src — broken"
    assert acts[0].labels == ["scraper-health", "kind:broken"]
    assert st.kind == "broken" and st.last_comment_at == NOW
    assert _plan([R("degraded")] * 1)[0] == []
    assert _plan([R("degraded")] * 2)[0][0].kind == "degraded"
    assert _plan([R("site_down", "transport")] * 2)[0] == []
    assert _plan([R("site_down", "transport")] * 3)[0][0].kind == "site-down"


def test_streak_is_by_verdict_and_ends_at_healthy_or_acked():
    assert _plan([R("broken"), R("healthy"), R("broken")])[0] == []
    assert _plan([R("broken"), R("broken", acked=True)])[0] == []
    assert _plan([R("broken"), R("degraded")])[0] == []
    assert h.bad_streak([R("broken"), R("degraded"), R("healthy"), R("broken")]) == 2


def test_long_block_is_relabelled_broken():
    blocked = [R("site_down", "blocked")]
    assert h.desired_issue_kind(blocked * 6) == "site-down"
    assert h.desired_issue_kind(blocked * 7) == "broken"
    st = h.IssueState(12, "site-down", NOW - dt.timedelta(days=1), "site_down|blocked|")
    acts, new = _plan(blocked * 7, st)
    assert [type(a) for a in acts] == [h.RelabelIssue, h.CommentIssue]
    assert acts[0].labels == ["scraper-health", "kind:broken"] and new.kind == "broken"
    # a 5xx streak never becomes "broken"
    assert h.desired_issue_kind([R("site_down", "http_5xx")] * 10) == "site-down"


def test_open_issue_comments_only_on_change_or_weekly():
    st = h.IssueState(7, "broken", NOW - dt.timedelta(days=1), "broken|exception|")
    runs = [R("broken", "exception")] * 3
    assert _plan(runs, st)[0] == []                                   # unchanged
    acts, new = _plan([R("broken", "http_gone")] + runs, st)           # changed
    assert [a.body_kind for a in acts] == ["update"] and new.last_signature == "broken|http_gone|"
    assert new.last_comment_at == NOW
    week = h.IssueState(7, "broken", NOW - dt.timedelta(days=7), "broken|exception|")
    acts, new = _plan(runs, week)                                     # weekly cap
    assert [a.body_kind for a in acts] == ["weekly"] and new.last_comment_at == NOW
    six = h.IssueState(7, "broken", NOW - dt.timedelta(days=6, hours=23), "broken|exception|")
    assert _plan(runs, six)[0] == []


def test_rule_change_counts_as_change():
    st = h.IssueState(3, "degraded", NOW, "degraded||source/count_drop")
    acts, _ = _plan([R("degraded", rules=["source/coverage_drop"])] * 2, st)
    assert [a.body_kind for a in acts] == ["update"]


def test_still_bad_below_threshold_keeps_issue_open():
    # an issue is open for site-down; one broken run: comment, don't close/open
    st = h.IssueState(4, "site-down", NOW - dt.timedelta(days=1), "site_down|transport|")
    acts, new = _plan([R("broken", "exception")] + [R("site_down", "transport")] * 3, st)
    assert [type(a) for a in acts] == [h.CommentIssue] and new.number == 4


def test_first_healthy_run_closes():
    st = h.IssueState(9, "broken", NOW, "broken|exception|")
    acts, new = _plan([R("healthy"), R("broken"), R("broken")], st)
    assert acts == [h.CloseIssue("recovered")] and new == h.IssueState()
    acts, _ = _plan([R("degraded", acked=True)], st)
    assert acts == [h.CloseIssue("recovered")]


def test_issue_body_has_what_a_repair_session_needs():
    ctx = h.IssueContext(
        source_slug="jazzin-amsterdam", module="jazzin_amsterdam", repo="jpjagt/cartelita",
        verdict="degraded", error_kind=None, error_message=None,
        fired=[h.FiredRule("source", "coverage_drop", 0.4, 0.6, "re-saw 40/100")],
        metrics={"source": M(60, 100, 40, 100, {}).to_json()},
        last_healthy=NOW - dt.timedelta(days=2), streak=2)
    body = h.render_issue_body(ctx)
    for needle in ["`degraded`", "coverage_drop", "re-saw 40/100", "2026-10-10",
                   "scraper/src/cartelera/scrapers/jazzin_amsterdam.py",
                   "jazzin_amsterdam_SOURCE.md", "scraper/tests/test_jazzin_amsterdam.py",
                   "cartelera dry-run jazzin_amsterdam", "AGENTS.md", "writing-a-scraper",
                   "https://github.com/jpjagt/cartelita/blob/main/"]:
        assert needle in body, needle
    broken = h.IssueContext("x", "x", None, "broken", "exception", "Traceback ...\nValueError: boom",
                            [], None, None, 2)
    assert "ValueError: boom" in h.render_issue_body(broken)
    assert "never recorded" in h.render_issue_body(broken)
