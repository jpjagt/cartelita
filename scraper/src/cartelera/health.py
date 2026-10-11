"""Scraper health: verdicts, metrics, baselines and the issue state machine.

Design: docs/superpowers/specs/2026-10-12-scraper-health-design.md. Everything
here is pure (no DB, no network) so it can be unit-tested directly; `run.py`
does the I/O (snapshot → classify → write/hide → record → GitHub) and
`health_cli.py` the `cartelera health ...` commands.

Thresholds are starting values; tune them here and nowhere else.
"""
from __future__ import annotations

import datetime as dt
import statistics
import traceback
from dataclasses import dataclass, field
from typing import Any, Iterable

import httpx

from cartelera.types import ScrapedEvent

# --- verdicts ---------------------------------------------------------------

HEALTHY = "healthy"
DEGRADED = "degraded"
BROKEN = "broken"
SITE_DOWN = "site_down"
BAD_VERDICTS = (DEGRADED, BROKEN, SITE_DOWN)
# Verdicts after which the source's data was NOT written (cartelera run exits 1).
FAILED_VERDICTS = (BROKEN, SITE_DOWN)

# error_kind values
ERR_TRANSPORT = "transport"   # connect / DNS / timeout / protocol
ERR_HTTP_5XX = "http_5xx"
ERR_BLOCKED = "blocked"       # 403 / 429: site_down sub-kind
ERR_HTTP_GONE = "http_gone"   # 404 / 410: the listing URL moved
ERR_HTTP_4XX = "http_4xx"     # any other client error
ERR_EXCEPTION = "exception"   # parsing, validation, unknown category, ...

# --- thresholds -------------------------------------------------------------

BASELINE_WINDOW = 14          # healthy-or-acked runs the baseline medians over
BASELINE_MIN_RUNS = 3         # baseline-relative rules apply from this many runs

EMPTY_BASELINE_FLOOR = 3      # empty: baseline emitted >= this
COUNT_DROP_RATIO = 0.5        # count drop: emitted < ratio x baseline emitted
COUNT_DROP_BASELINE_FLOOR = 10
COVERAGE_MIN = 0.6            # coverage drop: reseen / known_upcoming < this
COVERAGE_KNOWN_FLOOR = 10     #   ... when known_upcoming >= this
HORIZON_RATIO = 0.5           # horizon shrink: horizon < ratio x baseline
HORIZON_BASELINE_FLOOR_DAYS = 14
FIELD_DROP = 0.3              # field drop: fill < baseline fill - this
FIELD_BASELINE_FLOOR = 0.5    #   ... when baseline fill >= this
# Per-venue scopes of a multi-venue source: the ratio rules (horizon, field)
# are skipped for venues whose baseline emitted is below this — a venue with a
# handful of events swings those ratios on noise alone.
VENUE_RATIO_RULES_MIN_EVENTS = 10
FILL_FIELDS = ("price", "start_time", "description")

HIDE_AFTER_MISSES = 3         # healthy runs an upcoming event may be missing

SITE_DOWN_ISSUE_STREAK = 3
BLOCKED_AS_BROKEN_STREAK = 7  # a block this long needs a code change
BROKEN_ISSUE_STREAK = 2
DEGRADED_ISSUE_STREAK = 2
COMMENT_INTERVAL = dt.timedelta(days=7)   # re-comment cap when nothing changed

ERROR_TAIL_CHARS = 4000

# issue kinds
KIND_SITE_DOWN = "site-down"
KIND_BROKEN = "broken"
KIND_DEGRADED = "degraded"
ISSUE_LABEL = "scraper-health"


# --- 2. error classification ------------------------------------------------

def _exception_chain(exc: BaseException) -> Iterable[BaseException]:
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        yield cur
        cur = cur.__cause__ or cur.__context__


def classify_exception(exc: BaseException) -> tuple[str, str]:
    """(verdict, error_kind) for a scrape that raised. Transport failures and
    5xx/403/429 anywhere in the exception chain mean the site is down or
    blocking us; 404/410 mean the URL moved (our code must change); anything
    else is a broken scraper."""
    for e in _exception_chain(exc):
        if isinstance(e, httpx.HTTPStatusError):
            status = e.response.status_code
            if status >= 500:
                return SITE_DOWN, ERR_HTTP_5XX
            if status in (403, 429):
                return SITE_DOWN, ERR_BLOCKED
            if status in (404, 410):
                return BROKEN, ERR_HTTP_GONE
            return BROKEN, ERR_HTTP_4XX
        if isinstance(e, httpx.TransportError):
            return SITE_DOWN, ERR_TRANSPORT
    return BROKEN, ERR_EXCEPTION


def error_tail(exc: BaseException, limit: int = ERROR_TAIL_CHARS) -> str:
    """The traceback's tail (the most useful end), truncated to `limit`."""
    text = "".join(traceback.format_exception(exc))
    return text if len(text) <= limit else "…" + text[-limit:]


# --- 1. metrics ---------------------------------------------------------------

@dataclass
class ScopeMetrics:
    """Metrics for one scope: a venue, or a whole source."""
    emitted: int
    known_upcoming: int
    reseen: int
    horizon_days: int | None
    fill: dict[str, float] = field(default_factory=dict)

    @property
    def coverage(self) -> float | None:
        return self.reseen / self.known_upcoming if self.known_upcoming else None

    def to_json(self) -> dict[str, Any]:
        return {
            "emitted": self.emitted,
            "known_upcoming": self.known_upcoming,
            "reseen": self.reseen,
            "coverage": None if self.coverage is None else round(self.coverage, 4),
            "horizon_days": self.horizon_days,
            "fill": {k: round(v, 4) for k, v in self.fill.items()},
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> ScopeMetrics:
        return cls(
            emitted=d.get("emitted", 0),
            known_upcoming=d.get("known_upcoming", 0),
            reseen=d.get("reseen", 0),
            horizon_days=d.get("horizon_days"),
            fill=dict(d.get("fill") or {}),
        )


def _has(ev: ScrapedEvent, f: str) -> bool:
    if f == "start_time":
        return ev.start_time is not None or bool(ev.start_times)
    return bool(getattr(ev, f))


def compute_metrics(
    events: list[ScrapedEvent], known_upcoming: int, reseen: int, today: dt.date
) -> ScopeMetrics:
    """Metrics for one scope. `known_upcoming` / `reseen` come from the
    pre-write DB snapshot (run.py)."""
    n = len(events)
    return ScopeMetrics(
        emitted=n,
        known_upcoming=known_upcoming,
        reseen=reseen,
        horizon_days=(max(e.start_date for e in events) - today).days if n else None,
        fill={f: sum(_has(e, f) for e in events) / n for f in FILL_FIELDS} if n else {},
    )


def aggregate_metrics(scopes: Iterable[ScopeMetrics]) -> ScopeMetrics:
    """Source-level metrics from its venues' (fill weighted by emitted)."""
    scopes = list(scopes)
    emitted = sum(s.emitted for s in scopes)
    horizons = [s.horizon_days for s in scopes if s.horizon_days is not None]
    fill = (
        {f: sum(s.fill.get(f, 0.0) * s.emitted for s in scopes) / emitted for f in FILL_FIELDS}
        if emitted else {}
    )
    return ScopeMetrics(
        emitted=emitted,
        known_upcoming=sum(s.known_upcoming for s in scopes),
        reseen=sum(s.reseen for s in scopes),
        horizon_days=max(horizons) if horizons else None,
        fill=fill,
    )


@dataclass
class RunMetrics:
    source: ScopeMetrics
    venues: dict[str, ScopeMetrics]

    def to_json(self, fired: list[FiredRule]) -> dict[str, Any]:
        return {
            "source": self.source.to_json(),
            "venues": {k: v.to_json() for k, v in self.venues.items()},
            "fired": [r.to_json() for r in fired],
        }


# --- 2. baseline + degraded rules ---------------------------------------------

@dataclass
class Baseline:
    runs: int
    emitted: float
    horizon_days: float | None
    fill: dict[str, float]


def compute_baseline(history: list[ScopeMetrics]) -> Baseline | None:
    """Median of each metric over a scope's healthy-or-acked runs (newest
    first, already limited to BASELINE_WINDOW by the caller). None below
    BASELINE_MIN_RUNS: cold start, baseline-relative rules don't apply."""
    history = history[:BASELINE_WINDOW]
    if len(history) < BASELINE_MIN_RUNS:
        return None
    horizons = [m.horizon_days for m in history if m.horizon_days is not None]
    fill: dict[str, float] = {}
    for f in FILL_FIELDS:
        vals = [m.fill[f] for m in history if f in m.fill]
        if vals:
            fill[f] = statistics.median(vals)
    return Baseline(
        runs=len(history),
        emitted=statistics.median(m.emitted for m in history),
        horizon_days=statistics.median(horizons) if horizons else None,
        fill=fill,
    )


@dataclass
class FiredRule:
    scope: str          # "source" or "venue:<slug>"
    rule: str           # empty | count_drop | coverage_drop | horizon_shrink | field_drop:<f>
    value: float | None
    reference: float | None   # baseline value (or the absolute threshold)
    detail: str

    @property
    def key(self) -> str:
        return f"{self.scope}/{self.rule}"

    def to_json(self) -> dict[str, Any]:
        return {"scope": self.scope, "rule": self.rule, "value": self.value,
                "reference": self.reference, "detail": self.detail}

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> FiredRule:
        return cls(d["scope"], d["rule"], d.get("value"), d.get("reference"), d.get("detail", ""))


def evaluate_rules(
    scope: str, m: ScopeMetrics, b: Baseline | None, *, small_scope_guard: bool = False
) -> list[FiredRule]:
    """The degraded rules for one scope. The coverage rule needs no baseline
    (it compares against the DB's known events) so it applies from the first
    run; the others are baseline-relative and skipped on cold start.
    `small_scope_guard` (venues of a multi-venue source) skips the ratio rules
    for venues too small for them to be meaningful."""
    fired: list[FiredRule] = []
    cov = m.coverage
    if m.known_upcoming >= COVERAGE_KNOWN_FLOOR and cov is not None and cov < COVERAGE_MIN:
        fired.append(FiredRule(
            scope, "coverage_drop", round(cov, 3), COVERAGE_MIN,
            f"re-saw {m.reseen}/{m.known_upcoming} known upcoming events "
            f"({cov:.0%} < {COVERAGE_MIN:.0%})"))
    if b is None:
        return fired

    if m.emitted == 0 and b.emitted >= EMPTY_BASELINE_FLOOR:
        fired.append(FiredRule(scope, "empty", 0, b.emitted,
                               f"0 events (baseline {b.emitted:g})"))
    elif b.emitted >= COUNT_DROP_BASELINE_FLOOR and m.emitted < COUNT_DROP_RATIO * b.emitted:
        fired.append(FiredRule(scope, "count_drop", m.emitted, b.emitted,
                               f"{m.emitted} events < {COUNT_DROP_RATIO:g} × baseline {b.emitted:g}"))

    if small_scope_guard and b.emitted < VENUE_RATIO_RULES_MIN_EVENTS:
        return fired
    if (b.horizon_days is not None and b.horizon_days >= HORIZON_BASELINE_FLOOR_DAYS
            and m.horizon_days is not None and m.horizon_days < HORIZON_RATIO * b.horizon_days):
        fired.append(FiredRule(scope, "horizon_shrink", m.horizon_days, b.horizon_days,
                               f"horizon {m.horizon_days}d < {HORIZON_RATIO:g} × baseline "
                               f"{b.horizon_days:g}d"))
    if m.emitted:
        for f in FILL_FIELDS:
            base = b.fill.get(f)
            cur = m.fill.get(f)
            if base is None or cur is None or base < FIELD_BASELINE_FLOOR:
                continue
            if cur < base - FIELD_DROP:
                fired.append(FiredRule(scope, f"field_drop:{f}", round(cur, 3), round(base, 3),
                                       f"{f} on {cur:.0%} of events (baseline {base:.0%})"))
    return fired


def evaluate_run(
    metrics: RunMetrics,
    source_history: list[ScopeMetrics],
    venue_history: dict[str, list[ScopeMetrics]],
) -> list[FiredRule]:
    """All rules for a run. A single-venue source is evaluated once (source ==
    venue); a multi-venue source per venue AND as a whole (the aggregate
    catches truncation spread thinly over many small venues)."""
    fired = evaluate_rules("source", metrics.source, compute_baseline(source_history))
    if len(metrics.venues) > 1:
        for slug, vm in metrics.venues.items():
            fired += evaluate_rules(
                f"venue:{slug}", vm, compute_baseline(venue_history.get(slug, [])),
                small_scope_guard=True)
    return fired


def verdict_for(fired: list[FiredRule]) -> str:
    return DEGRADED if fired else HEALTHY


# --- 5. streaks → issue state machine -----------------------------------------

@dataclass
class RunSummary:
    """What the state machine needs from a scrape_run row."""
    verdict: str
    error_kind: str | None = None
    rules: list[str] = field(default_factory=list)   # FiredRule.key values
    acked: bool = False
    started_at: dt.datetime | None = None

    @property
    def is_good(self) -> bool:
        return self.verdict == HEALTHY or self.acked

    @property
    def signature(self) -> str:
        return f"{self.verdict}|{self.error_kind or ''}|{','.join(sorted(self.rules))}"


@dataclass
class IssueState:
    number: int | None = None
    kind: str | None = None
    last_comment_at: dt.datetime | None = None
    last_signature: str | None = None


@dataclass
class OpenIssue:
    kind: str
    title: str
    labels: list[str]


@dataclass
class CommentIssue:
    body_kind: str   # "update" | "weekly" | "relabel"


@dataclass
class RelabelIssue:
    kind: str
    title: str
    labels: list[str]


@dataclass
class CloseIssue:
    reason: str      # "recovered" | "acked"


IssueAction = OpenIssue | CommentIssue | RelabelIssue | CloseIssue


def _streak(runs: list[RunSummary], pred) -> int:
    n = 0
    for r in runs:
        if r.acked or not pred(r):
            break
        n += 1
    return n


def desired_issue_kind(runs: list[RunSummary]) -> str | None:
    """The issue kind the newest runs (newest first) call for, or None. An
    acked or healthy run ends every streak."""
    if not runs or runs[0].is_good:
        return None
    v = runs[0].verdict
    same = _streak(runs, lambda r: r.verdict == v)
    if v == SITE_DOWN:
        blocked = _streak(runs, lambda r: r.verdict == SITE_DOWN and r.error_kind == ERR_BLOCKED)
        if blocked >= BLOCKED_AS_BROKEN_STREAK:
            return KIND_BROKEN
        return KIND_SITE_DOWN if same >= SITE_DOWN_ISSUE_STREAK else None
    if v == BROKEN:
        return KIND_BROKEN if same >= BROKEN_ISSUE_STREAK else None
    if v == DEGRADED:
        return KIND_DEGRADED if same >= DEGRADED_ISSUE_STREAK else None
    return None


def bad_streak(runs: list[RunSummary]) -> int:
    """Consecutive non-healthy, non-acked runs, newest first."""
    return _streak(runs, lambda r: not r.is_good)


def issue_title(source_slug: str, kind: str) -> str:
    return f"scraper: {source_slug} — {kind}"


def issue_labels(kind: str) -> list[str]:
    return [ISSUE_LABEL, f"kind:{kind}"]


def plan_issue_actions(
    source_slug: str, runs: list[RunSummary], state: IssueState, now: dt.datetime
) -> tuple[list[IssueAction], IssueState]:
    """Decide the GitHub actions after a run (runs newest first, the run just
    recorded at index 0). Returns the actions and the resulting state; an
    OpenIssue's number is filled into the state by the executor."""
    if not runs:
        return [], state
    latest = runs[0]
    new = IssueState(state.number, state.kind, state.last_comment_at, state.last_signature)

    if state.number is not None:
        if latest.is_good:
            return [CloseIssue("recovered")], IssueState()
        actions: list[IssueAction] = []
        want = desired_issue_kind(runs)
        if want is not None and want != state.kind:
            actions.append(RelabelIssue(want, issue_title(source_slug, want), issue_labels(want)))
            new.kind = want
            actions.append(CommentIssue("relabel"))
        elif latest.signature != state.last_signature:
            actions.append(CommentIssue("update"))
        elif state.last_comment_at is None or now - state.last_comment_at >= COMMENT_INTERVAL:
            actions.append(CommentIssue("weekly"))
        if actions:
            new.last_comment_at = now
        new.last_signature = latest.signature
        return actions, new

    want = desired_issue_kind(runs)
    if want is None:
        return [], new
    new.kind = want
    new.last_comment_at = now
    new.last_signature = latest.signature
    return [OpenIssue(want, issue_title(source_slug, want), issue_labels(want))], new


# --- issue text -----------------------------------------------------------------

@dataclass
class IssueContext:
    """Everything the issue body needs about a source and its latest run."""
    source_slug: str
    module: str | None                 # scraper module name, e.g. "jazzin_amsterdam"
    repo: str | None                   # "owner/name", for links
    verdict: str
    error_kind: str | None
    error_message: str | None
    fired: list[FiredRule]
    metrics: dict[str, Any] | None
    last_healthy: dt.datetime | None
    streak: int


def _link(repo: str | None, path: str) -> str:
    return f"[`{path}`](https://github.com/{repo}/blob/main/{path})" if repo else f"`{path}`"


def _rules_table(fired: list[FiredRule]) -> str:
    if not fired:
        return ""
    rows = ["| scope | rule | value | baseline / threshold | detail |", "|---|---|---|---|---|"]
    for r in fired:
        rows.append(f"| {r.scope} | {r.rule} | {r.value} | {r.reference} | {r.detail} |")
    return "\n".join(rows)


def render_status(ctx: IssueContext) -> str:
    """The run-status part (used for the issue body and update comments)."""
    parts = [f"**Verdict:** `{ctx.verdict}`"
             + (f" (error kind `{ctx.error_kind}`)" if ctx.error_kind else "")
             + f" — {ctx.streak} consecutive bad run(s).",
             f"**Last healthy run:** {ctx.last_healthy.isoformat(timespec='minutes') if ctx.last_healthy else 'never recorded'}."]
    if ctx.fired:
        parts.append("**Rules fired** (metrics vs baseline = median of the last "
                     f"{BASELINE_WINDOW} healthy-or-acked runs):\n\n" + _rules_table(ctx.fired))
    if ctx.metrics and ctx.metrics.get("source"):
        s = ctx.metrics["source"]
        parts.append(f"**Source metrics:** emitted {s.get('emitted')}, known upcoming "
                     f"{s.get('known_upcoming')}, re-seen {s.get('reseen')}, coverage "
                     f"{s.get('coverage')}, horizon {s.get('horizon_days')}d, fill {s.get('fill')}.")
    if ctx.error_message:
        parts.append("**Traceback (tail):**\n\n```\n" + ctx.error_message.strip() + "\n```")
    return "\n\n".join(parts)


def render_issue_body(ctx: IssueContext) -> str:
    mod = ctx.module or "<module>"
    base = "scraper/src/cartelera/scrapers"
    files = [
        f"- scraper: {_link(ctx.repo, f'{base}/{mod}.py')}",
        f"- source map: {_link(ctx.repo, f'{base}/{mod}_SOURCE.md')}",
        f"- test: {_link(ctx.repo, f'scraper/tests/test_{mod}.py')} "
        f"(fixtures: `scraper/tests/fixtures/{mod}*`)",
        f"- try it: `cd scraper && uv run cartelera dry-run {mod}`",
    ]
    return "\n\n".join([
        f"Scraper health flagged source `{ctx.source_slug}`.",
        render_status(ctx),
        "**Files**\n\n" + "\n".join(files),
        "**Verdicts:** `site_down` = the site is down or blocking us (transport error, "
        "5xx, 403/429) — usually wait it out; `broken` = the scraper raised (or the "
        "listing URL 404s) — needs a code fix; `degraded` = it ran but the output is "
        "implausible against its baseline (fewer events, known events not re-seen, "
        "shorter horizon, a field gone) — likely a partial break such as pagination "
        "or a dead selector. Last good data is kept; nothing is hidden while bad.",
        "---\n_For a repairing agent:_ follow `AGENTS.md` and the `writing-a-scraper` "
        "skill (`.claude/skills/writing-a-scraper/`). Re-verify the scraper against the "
        "live site field by field, refresh the fixture, keep the tests green, and update "
        "the `_SOURCE.md`. If the site legitimately changed (e.g. a season break), say so "
        f"instead — the owner can run `cartelera health ack {ctx.source_slug}`.",
    ])


def render_comment(kind: str, ctx: IssueContext) -> str:
    head = {
        "update": "Still failing, and something changed:",
        "weekly": "Still failing (weekly reminder):",
        "relabel": f"Re-classified as `{desired_kind_label(ctx)}`:",
    }.get(kind, "Update:")
    return head + "\n\n" + render_status(ctx)


def desired_kind_label(ctx: IssueContext) -> str:
    if ctx.verdict == SITE_DOWN and ctx.error_kind == ERR_BLOCKED:
        return f"{KIND_BROKEN} (blocked for {BLOCKED_AS_BROKEN_STREAK}+ nights: needs a code change)"
    return ctx.verdict


def render_close_comment(reason: str, source_slug: str) -> str:
    if reason == "acked":
        return (f"Acknowledged via `cartelera health ack {source_slug}`: the latest run "
                "now counts as baseline. Closing.")
    return f"Recovered: `{source_slug}` had a healthy run. Closing."
