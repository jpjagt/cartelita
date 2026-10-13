"""DB + GitHub side of scraper health: syncing a source's issue (and the
long-degraded venues on its review issue) after a run, and the `cartelera
health [<source>|ack|rekey]` commands. Decisions live in the pure
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


def view(run: ScrapeRun) -> health.RunView:
    return health.RunView(run.verdict, run.acked, run.metrics, run.started_at)


def summarize(run: ScrapeRun) -> health.RunSummary:
    """For the SOURCE issue: only source-level rules make its signature (a
    venue-level rule never degrades the source; see sync_degraded_venues)."""
    return health.RunSummary(
        verdict=run.verdict, error_kind=run.error_kind,
        rules=[f.key for f in health.source_rules(view(run).fired)],
        acked=run.acked, started_at=run.started_at)


def last_healthy(session: Session, source_slug: str) -> dt.datetime | None:
    return session.scalar(
        select(ScrapeRun.started_at)
        .where(ScrapeRun.source_slug == source_slug,
               or_(ScrapeRun.verdict == health.HEALTHY, ScrapeRun.acked.is_(True)))
        .order_by(ScrapeRun.started_at.desc()).limit(1))


def module_of(source_slug: str) -> str | None:
    entry = REGISTRY.get(source_slug)
    return type(entry[0]).__module__.rsplit(".", 1)[-1] if entry else None


def issue_context(
    session: Session, source_slug: str, runs: list[ScrapeRun], repo: str | None
) -> health.IssueContext:
    latest = runs[0]
    return health.IssueContext(
        source_slug=source_slug,
        module=module_of(source_slug),
        repo=repo,
        verdict=latest.verdict,
        error_kind=latest.error_kind,
        error_message=latest.error_message,
        fired=health.source_rules(view(latest).fired),
        metrics=latest.metrics,
        last_healthy=last_healthy(session, source_slug),
        streak=health.bad_streak([summarize(r) for r in runs]),
        degraded_venues=len(view(latest).degraded_venues),
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
                    tracker.comment(state.number, health.render_close_comment(
                        a.reason, source_slug, ctx.degraded_venues))
                    tracker.close_issue(state.number)
    _save_state(session, sh, new)
    return actions


def venue_alerts(
    session: Session, runs: list[ScrapeRun], min_streak: int = 1
) -> list[dict]:
    """The venues degraded in the newest run with metrics, with their streak
    (consecutive degraded runs) and fired rules: [{slug, name, streak, rules:
    [detail], rule_names}], longest streak first. Only those with streak >=
    `min_streak`."""
    views = [view(r) for r in runs]
    latest = next((v for v in views if v.metrics is not None), None)
    if latest is None:
        return []
    bad = latest.degraded_venues
    names = dict(session.execute(select(Venue.slug, Venue.name).where(Venue.slug.in_(bad))).all())
    alerts = []
    for slug, rules in bad.items():
        streak = health.venue_streak(views, slug)
        if streak >= min_streak:
            alerts.append({"slug": slug, "name": names.get(slug, slug), "streak": streak,
                           "rules": [f"{r.rule}: {r.detail}" for r in rules],
                           "rule_names": [r.rule for r in rules]})
    return sorted(alerts, key=lambda a: (-a["streak"], a["slug"]))


def sync_degraded_venues(
    session: Session, source_slug: str, tracker: IssueTracker, now: dt.datetime | None = None,
) -> str | None:
    """List venues degraded on their own for VENUE_REVIEW_STREAK+ runs on the
    source's rolling review issue (cartelera.discovery): comment when the set
    or their rules change, else at most weekly; one "cleared" comment when
    none are left. Never touches the source issue. Returns the posted kind."""
    from cartelera.discovery import post_review, render_degraded_review

    now = now or _now()
    runs = recent_runs(session, source_slug)
    if not runs or runs[0].metrics is None:
        return None  # broken / site_down: nothing new about venues
    alerts = venue_alerts(session, runs, min_streak=health.VENUE_REVIEW_STREAK)
    sig = health.venue_review_signature({a["slug"]: a["rule_names"] for a in alerts})
    sh = session.get(SourceHealth, source_slug) or SourceHealth(source_slug=source_slug)
    kind = health.plan_venue_review(sig, sh.venue_review_signature, sh.venue_review_comment_at, now)
    if kind == "cleared" and not (sh.review_issue_number and tracker.is_open(sh.review_issue_number)):
        kind = None  # nothing open to tell; just forget the old set
        sh.venue_review_signature = None
    if kind is not None:
        module = module_of(source_slug)
        post_review(session, source_slug, tracker,
                    render_degraded_review(source_slug, module, alerts, kind, first=True),
                    render_degraded_review(source_slug, module, alerts, kind, first=False))
        sh = session.get(SourceHealth, source_slug)
        sh.venue_review_signature = sig
        sh.venue_review_comment_at = now
    session.add(sh)
    session.commit()
    return kind


# --- cartelera health ... -------------------------------------------------------

def _source_venue_ids(session: Session, source_slug: str) -> list[int]:
    """The source's code-defined venues plus the ones it discovered at run
    time (cartelera.discovery)."""
    entry = REGISTRY.get(source_slug)
    if entry is None:
        return []
    return list(session.scalars(
        select(Venue.id).where(or_(Venue.slug.in_([v.slug for v in entry[1].venues]),
                                   Venue.discovered_by == source_slug))))


def ack(
    session: Session, source_slug: str, tracker: IssueTracker, today: dt.date | None = None
) -> str:
    """Accept the latest run as correct: mark it acked (it joins the baseline
    and ends the bad streak), hide the source's visible upcoming events that
    run did not see (reversible: they un-hide if they reappear), and close the
    source's issue. Only a data-writing run (healthy / degraded) can vouch for
    what's gone; acking a broken / site_down run hides nothing."""
    today = today or dt.date.today()
    runs = recent_runs(session, source_slug, limit=1)
    if not runs:
        raise ValueError(f"no recorded runs for source {source_slug!r}")
    run = runs[0]
    run.acked = True
    hidden = 0
    if run.verdict in (health.HEALTHY, health.DEGRADED):
        venue_ids = _source_venue_ids(session, source_slug)
        hidden = session.execute(
            update(Event).where(
                Event.venue_id.in_(venue_ids), Event.start_date >= today,
                Event.hidden_at.is_(None),
                or_(Event.last_seen_at.is_(None), Event.last_seen_at < run.started_at))
            .values(hidden_at=_now()).execution_options(synchronize_session=False)
        ).rowcount
    session.commit()
    sh, state = _load_state(session, source_slug)
    msg = (f"acked run #{run.id} ({run.verdict}, {run.started_at:%Y-%m-%d %H:%M}); "
           f"hid {hidden} upcoming events it did not see")
    if state.number is not None:
        tracker.comment(state.number, health.render_close_comment("acked", source_slug))
        tracker.close_issue(state.number)
        msg += f"; closed issue #{state.number}"
    _save_state(session, sh, health.IssueState())
    return msg


def ack_venue(
    session: Session, source_slug: str, venue_slug: str, today: dt.date | None = None
) -> str:
    """Accept one venue's state in the source's latest run as its new normal
    (e.g. it has no programme any more): the run is recorded as acked for that
    venue (metrics["acked_venues"]) — its baseline restarts from this run, its
    coverage reference becomes this run, its degraded streak ends — and the
    venue's visible upcoming events that run did not see are hidden
    (reversible). The source issue and the other venues are untouched."""
    today = today or dt.date.today()
    entry = REGISTRY.get(source_slug)
    venue = session.scalar(select(Venue).where(Venue.slug == venue_slug))
    if venue is None or venue.id not in _source_venue_ids(session, source_slug):
        raise ValueError(f"{venue_slug!r} is not a venue of source {source_slug!r}")
    if entry is not None and len(entry[1].venues) == 1 and not session.scalar(
            select(Venue.id).where(Venue.discovered_by == source_slug).limit(1)):
        raise ValueError(f"{source_slug!r} has a single venue: use "
                         f"`cartelera health ack {source_slug}`")
    runs = recent_runs(session, source_slug, limit=1)
    if not runs or not view(runs[0]).wrote_data:
        raise ValueError(f"the latest {source_slug} run wrote no data (or there is none); "
                         "a venue can only be acked against a healthy/degraded run")
    run = runs[0]
    run.metrics = {**run.metrics,
                   "acked_venues": sorted(view(run).acked_venues | {venue_slug})}
    hidden = session.execute(
        update(Event).where(
            Event.venue_id == venue.id, Event.start_date >= today, Event.hidden_at.is_(None),
            or_(Event.last_seen_at.is_(None), Event.last_seen_at < run.started_at))
        .values(hidden_at=_now()).execution_options(synchronize_session=False)
    ).rowcount
    session.commit()
    return (f"acked venue {venue_slug} in run #{run.id} ({run.verdict}, "
            f"{run.started_at:%Y-%m-%d %H:%M}); hid {hidden} of its upcoming events "
            "that run did not see")


def status_lines(session: Session) -> list[str]:
    """One line per source: latest verdict, bad streak, venues degraded on
    their own (latest run), last healthy run, open issue."""
    slugs = sorted(set(REGISTRY) | set(session.scalars(select(ScrapeRun.source_slug).distinct())))
    lines = [f"{'source':32} {'latest':10} {'streak':>6} {'venues':>6}  {'last healthy':16}  issue"]
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
        lv = next((view(r) for r in runs if r.metrics is not None), None)
        n_bad = len(set(lv.degraded_venues) - lv.acked_venues) if lv and not lv.acked else 0
        lines.append(
            f"{slug:32} {latest:10} {health.bad_streak(summaries):>6} {n_bad or '-':>6}  "
            f"{lh.strftime('%Y-%m-%d %H:%M') if lh else 'never':16}  {issue}")
    return lines


def detail_lines(session: Session, source_slug: str) -> list[str]:
    """`cartelera health <source>`: its state, plus every venue degraded on
    its own in the latest run, with the fired rules and its streak."""
    runs = recent_runs(session, source_slug)
    if not runs:
        if source_slug not in REGISTRY:
            raise ValueError(f"unknown source {source_slug!r}")
        return [f"{source_slug}: never run"]
    latest = runs[0]
    sh = session.get(SourceHealth, source_slug)
    lh = last_healthy(session, source_slug)
    lines = [
        f"{source_slug}",
        f"  latest run   #{latest.id} {latest.verdict}{' (acked)' if latest.acked else ''} "
        f"at {latest.started_at:%Y-%m-%d %H:%M}",
        f"  bad streak   {health.bad_streak([summarize(r) for r in runs])}",
        f"  last healthy {lh.strftime('%Y-%m-%d %H:%M') if lh else 'never'}",
        f"  issue        " + (f"#{sh.issue_number} ({sh.issue_kind})"
                              if sh and sh.issue_number else "-"),
        f"  review issue " + (f"#{sh.review_issue_number}"
                              if sh and sh.review_issue_number else "-"),
    ]
    if latest.error_kind:
        lines.append(f"  error        {latest.error_kind}")
    for r in health.source_rules(view(latest).fired):
        lines.append(f"  source rule  {r.rule}: {r.detail}")
    alerts = venue_alerts(session, runs)
    if not alerts:
        lines.append("  degraded venues: none")
        return lines
    lines.append(f"  degraded venues: {len(alerts)} (runs = consecutive degraded runs; "
                 f">= {health.VENUE_REVIEW_STREAK} → on the review issue)")
    width = max(len(a["slug"]) for a in alerts)
    for a in alerts:
        lines.append(f"    {a['slug']:{width}}  {a['streak']:>3} runs  {a['name']}")
        for rule in a["rules"]:
            lines.append(f"    {'':{width}}            {rule}")
    lines.append(f"  accept a venue's new state: cartelera health ack {source_slug} <venue>")
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
    numeric) external_id at once (instead of after 3 healthy runs, with old
    and new rows visible side by side meanwhile) and ack that run. Dry-run
    unless `apply`."""
    if source_slug not in REKEYABLE:
        raise ValueError(f"rekey supports {sorted(REKEYABLE)}, not {source_slug!r}")
    today = today or dt.date.today()
    venue_ids = _source_venue_ids(session, source_slug)
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
    return (f"hid {n} upcoming legacy-keyed {source_slug} events; "
            + ack(session, source_slug, tracker, today=today))


USAGE = ("usage: cartelera health [<source> | ack <source> [<venue>] | "
         "rekey <source> [--apply]]")


def main(session: Session, args: list[str], tracker: IssueTracker) -> int:
    """`cartelera health [<source> | ack <source> [<venue>] | rekey <source> [--apply]]`."""
    try:
        if not args:
            print("\n".join(status_lines(session)))
            return 0
        if args[0] == "ack" and len(args) == 2:
            print(ack(session, args[1], tracker))
            return 0
        if args[0] == "ack" and len(args) == 3:
            print(ack_venue(session, args[1], args[2]))
            return 0
        if args[0] == "rekey" and len(args) in (2, 3) and args[2:] in ([], ["--apply"]):
            print(rekey(session, args[1], tracker, apply=args[2:] == ["--apply"]))
            return 0
        if len(args) == 1 and args[0] not in ("ack", "rekey"):
            print("\n".join(detail_lines(session, args[0])))
            return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(USAGE, file=sys.stderr)
    return 1
