"""DB + GitHub side of scraper health: syncing a source's issue after a run,
and the `cartelera health [ack|rekey]` commands. Decisions live in the pure
`cartelera.health`; this module only loads state, executes, and persists."""
from __future__ import annotations

import datetime as dt
import sys

from sqlalchemy import select, or_, update
from sqlalchemy.orm import Session

from cartelera import health
from cartelera.github import IssueTracker
from cartelera.models import Event, ScrapeRun, SourceHealth, Venue
from cartelera.scrapers import REGISTRY

RECENT_RUNS = 30  # enough history for every streak threshold


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def recent_runs(session: Session, source_slug: str, limit: int = RECENT_RUNS) -> list[ScrapeRun]:
    return list(session.scalars(
        select(ScrapeRun).where(ScrapeRun.source_slug == source_slug)
        .order_by(ScrapeRun.started_at.desc(), ScrapeRun.id.desc()).limit(limit)
    ))


def summarize(run: ScrapeRun) -> health.RunSummary:
    fired = [health.FiredRule.from_json(f) for f in (run.metrics or {}).get("fired", [])]
    return health.RunSummary(
        verdict=run.verdict, error_kind=run.error_kind, rules=[f.key for f in fired],
        acked=run.acked, started_at=run.started_at)


def last_healthy(session: Session, source_slug: str) -> dt.datetime | None:
    return session.scalar(
        select(ScrapeRun.started_at)
        .where(ScrapeRun.source_slug == source_slug,
               or_(ScrapeRun.verdict == health.HEALTHY, ScrapeRun.acked.is_(True)))
        .order_by(ScrapeRun.started_at.desc()).limit(1))


def _module_of(source_slug: str) -> str | None:
    entry = REGISTRY.get(source_slug)
    return type(entry[0]).__module__.rsplit(".", 1)[-1] if entry else None


def issue_context(
    session: Session, source_slug: str, runs: list[ScrapeRun], repo: str | None
) -> health.IssueContext:
    latest = runs[0]
    return health.IssueContext(
        source_slug=source_slug,
        module=_module_of(source_slug),
        repo=repo,
        verdict=latest.verdict,
        error_kind=latest.error_kind,
        error_message=latest.error_message,
        fired=[health.FiredRule.from_json(f) for f in (latest.metrics or {}).get("fired", [])],
        metrics=latest.metrics,
        last_healthy=last_healthy(session, source_slug),
        streak=health.bad_streak([summarize(r) for r in runs]),
    )


def _load_state(session: Session, source_slug: str) -> tuple[SourceHealth, health.IssueState]:
    sh = session.get(SourceHealth, source_slug) or SourceHealth(source_slug=source_slug)
    return sh, health.IssueState(sh.issue_number, sh.issue_kind, sh.last_comment_at, sh.last_signature)


def _save_state(session: Session, sh: SourceHealth, state: health.IssueState) -> None:
    sh.issue_number = state.number
    sh.issue_kind = state.kind
    sh.last_comment_at = state.last_comment_at
    sh.last_signature = state.last_signature
    session.add(sh)
    session.commit()


def sync_issue(
    session: Session, source_slug: str, tracker: IssueTracker, now: dt.datetime | None = None
) -> list[health.IssueAction]:
    """Open / comment / relabel / close the source's issue after a recorded
    run. Returns the actions taken (for tests and logs)."""
    now = now or _now()
    runs = recent_runs(session, source_slug)
    if not runs:
        return []
    sh, state = _load_state(session, source_slug)
    if state.number is not None and not tracker.is_open(state.number):
        state = health.IssueState()  # closed by hand: start over
    actions, new = health.plan_issue_actions(
        source_slug, [summarize(r) for r in runs], state, now)
    if actions:
        ctx = issue_context(session, source_slug, runs, tracker.repo)
        for a in actions:
            match a:
                case health.OpenIssue():
                    new.number = tracker.open_issue(a.title, health.render_issue_body(ctx), a.labels)
                case health.RelabelIssue():
                    tracker.update_issue(state.number, a.title, a.labels)
                case health.CommentIssue():
                    tracker.comment(state.number, health.render_comment(a.body_kind, ctx))
                case health.CloseIssue():
                    tracker.comment(state.number, health.render_close_comment(a.reason, source_slug))
                    tracker.close_issue(state.number)
    _save_state(session, sh, new)
    return actions


# --- cartelera health ... -------------------------------------------------------

def ack(session: Session, source_slug: str, tracker: IssueTracker) -> str:
    """Mark the latest run acked (it joins the baseline and ends the bad
    streak) and close the source's issue."""
    runs = recent_runs(session, source_slug, limit=1)
    if not runs:
        raise ValueError(f"no recorded runs for source {source_slug!r}")
    runs[0].acked = True
    session.commit()
    sh, state = _load_state(session, source_slug)
    msg = f"acked run #{runs[0].id} ({runs[0].verdict}, {runs[0].started_at:%Y-%m-%d %H:%M})"
    if state.number is not None:
        tracker.comment(state.number, health.render_close_comment("acked", source_slug))
        tracker.close_issue(state.number)
        msg += f"; closed issue #{state.number}"
    _save_state(session, sh, health.IssueState())
    return msg


def status_lines(session: Session) -> list[str]:
    """One line per source: latest verdict, bad streak, last healthy run, open
    issue."""
    slugs = sorted(set(REGISTRY) | set(session.scalars(select(ScrapeRun.source_slug).distinct())))
    lines = [f"{'source':32} {'latest':10} {'streak':>6}  {'last healthy':16}  issue"]
    for slug in slugs:
        runs = recent_runs(session, slug)
        if not runs:
            lines.append(f"{slug:32} {'never run':10}")
            continue
        summaries = [summarize(r) for r in runs]
        latest = runs[0].verdict + ("*" if runs[0].acked else "")
        lh = last_healthy(session, slug)
        sh = session.get(SourceHealth, slug)
        issue = f"#{sh.issue_number} ({sh.issue_kind})" if sh and sh.issue_number else "-"
        lines.append(
            f"{slug:32} {latest:10} {health.bad_streak(summaries):>6}  "
            f"{lh.strftime('%Y-%m-%d %H:%M') if lh else 'never':16}  {issue}")
    return lines


# jazzin.amsterdam switched from its (unstable, numeric) API ids to a
# content-derived external_id; `rekey` retires the legacy rows.
REKEYABLE = {"jazzin-amsterdam"}
_NUMERIC = "^[0-9]+$"


def rekey(
    session: Session, source_slug: str, tracker: IssueTracker, apply: bool,
    today: dt.date | None = None,
) -> str:
    """One-off after the jazzin key change: once a run with the new keys has
    succeeded, hide the source's upcoming events still on a legacy (purely
    numeric) external_id and ack that run so its coverage drop isn't flagged.
    Dry-run unless `apply`."""
    if source_slug not in REKEYABLE:
        raise ValueError(f"rekey supports {sorted(REKEYABLE)}, not {source_slug!r}")
    today = today or dt.date.today()
    _scraper, source = REGISTRY[source_slug]
    venue_ids = list(session.scalars(
        select(Venue.id).where(Venue.slug.in_([v.slug for v in source.venues]))))
    runs = recent_runs(session, source_slug, limit=1)
    if not runs or runs[0].verdict not in (health.HEALTHY, health.DEGRADED):
        raise ValueError(
            f"the latest {source_slug} run must have succeeded first: "
            f"`cartelera run {source_slug}`")
    run = runs[0]
    new_keyed = session.scalar(
        select(Event.id).where(
            Event.venue_id.in_(venue_ids), Event.last_seen_at >= run.started_at,
            ~Event.external_id.regexp_match(_NUMERIC)).limit(1))
    if new_keyed is None:
        raise ValueError(
            f"the latest {source_slug} run wrote no content-keyed events; "
            "deploy the new scraper and run it first")
    legacy = (Event.venue_id.in_(venue_ids), Event.start_date >= today,
              Event.hidden_at.is_(None), Event.external_id.regexp_match(_NUMERIC),
              or_(Event.last_seen_at.is_(None), Event.last_seen_at < run.started_at))
    n = len(session.scalars(select(Event.id).where(*legacy)).all())
    if not apply:
        return (f"[dry-run] would hide {n} upcoming legacy-keyed {source_slug} events "
                f"and ack run #{run.id} ({run.verdict}); re-run with --apply")
    session.execute(update(Event).where(*legacy).values(hidden_at=_now())
                    .execution_options(synchronize_session=False))
    session.commit()
    return f"hid {n} upcoming legacy-keyed {source_slug} events; " + ack(session, source_slug, tracker)


def main(session: Session, args: list[str], tracker: IssueTracker) -> int:
    """`cartelera health [ack <source> | rekey <source> [--apply]]`."""
    try:
        if not args:
            print("\n".join(status_lines(session)))
            return 0
        if args[0] == "ack" and len(args) == 2:
            print(ack(session, args[1], tracker))
            return 0
        if args[0] == "rekey" and len(args) in (2, 3) and args[2:] in ([], ["--apply"]):
            print(rekey(session, args[1], tracker, apply=args[2:] == ["--apply"]))
            return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("usage: cartelera health [ack <source> | rekey <source> [--apply]]", file=sys.stderr)
    return 1
