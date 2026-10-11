from __future__ import annotations
import datetime as dt
import importlib
import logging
import sys
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from cartelera import health
from cartelera.github import IssueTracker, make_tracker
from cartelera import health_ops
from cartelera.health_ops import sync_issue
from cartelera.models import ScrapeRun, Venue
from cartelera.db import make_engine, make_session_factory, ensure_database_exists
from cartelera.migrate import apply_migrations
from cartelera.seed import seed as seed_db
from cartelera.upsert import (
    upsert_venue_events, known_upcoming_snapshot, count_reseen, count_misses,
)
from cartelera.types import ScrapeResult, ScrapedEvent, SourceDefinition
from cartelera.scrapers import REGISTRY, load_all

logger = logging.getLogger(__name__)


def _group_events_by_venue(
    source: SourceDefinition, events: list[ScrapedEvent]
) -> dict[str, list[ScrapedEvent]]:
    """Resolve each event to one of the source's venues, failing fast on any
    mismatch. For a single-venue source, events may leave venue_slug unset (it
    resolves to the sole venue); a multi-venue source must set it on every
    event, and any slug outside the source's venue list — its editorial
    whitelist — is an error, never a silent drop."""
    known = {v.slug for v in source.venues}
    sole = source.venues[0].slug if len(source.venues) == 1 else None
    by_venue: dict[str, list[ScrapedEvent]] = {}
    for ev in events:
        slug = ev.venue_slug or sole
        if slug is None:
            raise ValueError(
                f"source {source.slug!r} has {len(source.venues)} venues, so every "
                f"event must set venue_slug; {ev.title!r} ({ev.start_date}) doesn't"
            )
        if slug not in known:
            raise ValueError(
                f"event {ev.title!r} ({ev.start_date}) names venue {slug!r}, which is "
                f"not among source {source.slug!r}'s venues {sorted(known)}"
            )
        by_venue.setdefault(slug, []).append(ev)
    return by_venue


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _write_source(
    session: Session, source: SourceDefinition, events: list[ScrapedEvent], today: dt.date
) -> tuple[str, list[health.FiredRule], dict, int]:
    """Classify a successful scrape and write it. Metrics are taken from a
    pre-write snapshot; then upsert (healthy + degraded) and, only when
    healthy, count misses / hide. Returns (verdict, fired, metrics_json,
    newly_hidden). Raises on any write-side failure (caller rolls back)."""
    by_venue = _group_events_by_venue(source, events)
    slugs = [v.slug for v in source.venues]
    venues = {v.slug: v for v in session.scalars(select(Venue).where(Venue.slug.in_(slugs)))}

    # 1. pre-write snapshot → metrics. Coverage is measured against what the
    # previous trusted run saw — healthy, or an acked data-writing run (the
    # same runs the baseline uses); none yet → coverage skipped. Degraded runs
    # don't move the reference: otherwise a persistently truncated scraper
    # would be flagged once, then measured against its own truncated view,
    # score healthy, and hide the real events through miss counting.
    seen_since = session.scalar(
        select(ScrapeRun.started_at)
        .where(ScrapeRun.source_slug == source.slug,
               or_(ScrapeRun.verdict == health.HEALTHY,
                   ScrapeRun.acked.is_(True) & (ScrapeRun.verdict == health.DEGRADED)))
        .order_by(ScrapeRun.started_at.desc()).limit(1))
    venue_metrics: dict[str, health.ScopeMetrics] = {}
    for slug in slugs:
        evs = by_venue.get(slug, [])
        venue = venues.get(slug)
        if venue is None:
            if evs:  # let the upsert raise its usual error
                upsert_venue_events(session, slug, evs)
            continue
        idx = known_upcoming_snapshot(session, venue.id, today, seen_since)
        venue_metrics[slug] = health.compute_metrics(
            evs, len(idx.ids), count_reseen(idx, evs), today)
    metrics = health.RunMetrics(
        source=health.aggregate_metrics(venue_metrics.values()), venues=venue_metrics)

    # 2. baseline + rules → verdict
    source_hist, venue_hist = _baseline_history(session, source.slug)
    fired = health.evaluate_run(metrics, source_hist, venue_hist)
    verdict = health.verdict_for(fired)

    # 3. write; 4. hide (healthy only)
    seen: set[int] = set()
    for slug, evs in by_venue.items():
        upsert_venue_events(session, slug, evs, seen_ids=seen)
    hidden = 0
    if verdict == health.HEALTHY:
        for venue in venues.values():
            hidden += count_misses(session, venue.id, seen, today)[1]
    return verdict, fired, metrics.to_json(fired), hidden


def _baseline_history(
    session: Session, source_slug: str
) -> tuple[list[health.ScopeMetrics], dict[str, list[health.ScopeMetrics]]]:
    """Metrics of the source's last BASELINE_WINDOW healthy-or-acked runs,
    newest first: source-level, and per venue."""
    rows = session.scalars(
        select(ScrapeRun)
        .where(ScrapeRun.source_slug == source_slug,
               ScrapeRun.metrics.is_not(None),
               or_(ScrapeRun.verdict == health.HEALTHY, ScrapeRun.acked.is_(True)))
        .order_by(ScrapeRun.started_at.desc(), ScrapeRun.id.desc())
        .limit(health.BASELINE_WINDOW)
    ).all()
    source_hist = [health.ScopeMetrics.from_json(r.metrics["source"]) for r in rows
                   if r.metrics.get("source")]
    venue_hist: dict[str, list[health.ScopeMetrics]] = {}
    for r in rows:
        for slug, vm in (r.metrics.get("venues") or {}).items():
            venue_hist.setdefault(slug, []).append(health.ScopeMetrics.from_json(vm))
    return source_hist, venue_hist


def run_one(
    session: Session,
    source_slug: str,
    *,
    tracker: IssueTracker | None = None,
    today: dt.date | None = None,
) -> ScrapeResult:
    """Scrape one source, classify the run, write/hide accordingly, record a
    scrape_run, and update its GitHub issue (see cartelera.health).

    The source's writes run in their own transaction: broken (any exception,
    including on write) and site_down runs roll back, keeping the last good
    data; degraded runs upsert but never count misses or hide."""
    scraper, source = REGISTRY[source_slug]
    today = today or dt.date.today()
    started = _now()
    events: list[ScrapedEvent] = []
    fired: list[health.FiredRule] = []
    metrics_json: dict | None = None
    error_kind = error_message = None
    hidden = 0
    try:
        events = scraper.scrape()
        verdict, fired, metrics_json, hidden = _write_source(session, source, events, today)
        session.commit()
    except Exception as exc:  # noqa: BLE001 - we want all failures isolated per source
        session.rollback()
        logger.exception("scrape failed for source %r", source_slug)
        verdict, error_kind = health.classify_exception(exc)
        error_message = health.error_tail(exc)
        error = f"{type(exc).__name__}: {exc}"
    else:
        error = None

    run = ScrapeRun(
        source_slug=source_slug, started_at=started, finished_at=_now(), verdict=verdict,
        error_kind=error_kind, error_message=error_message, metrics=metrics_json, acked=False)
    session.add(run)
    session.commit()

    try:
        sync_issue(session, source_slug, tracker or make_tracker())
    except Exception:  # noqa: BLE001 - GitHub trouble must never fail the scrape
        session.rollback()
        logger.exception("updating the health issue failed for source %r", source_slug)

    return ScrapeResult(
        source_slug=source_slug,
        ok=verdict not in health.FAILED_VERDICTS,
        events=events,
        error=error,
        verdict=verdict,
        fired=[r.detail if r.scope == "source" else f"{r.scope}: {r.detail}" for r in fired],
        hidden=hidden,
    )


def run_all(session: Session, tracker: IssueTracker | None = None) -> list[ScrapeResult]:
    return [run_one(session, slug, tracker=tracker) for slug in REGISTRY]


def _sources_in_category(category_slug: str) -> list[str]:
    """Registered source slugs where any venue lists `category_slug`."""
    return [
        slug for slug, (_scraper, source) in REGISTRY.items()
        if any(category_slug in v.category_slugs for v in source.venues)
    ]


def _sources_in_city(city_slug: str) -> list[str]:
    """Registered source slugs where any venue belongs to `city_slug`."""
    return [
        slug for slug, (_scraper, source) in REGISTRY.items()
        if any(v.city_slug == city_slug for v in source.venues)
    ]


def _resolve_run_targets(run_args: list[str]) -> list[str] | None:
    """Turn the `run` args into the ordered list of source slugs to scrape.

    Forms:
      (none) / all        -> every registered source
      :<city_slug>         -> every source with a venue in that city
      -c <category_slug>  -> every source with a venue in that category
      <slug>[,<slug>...]  -> the listed sources (comma- or space-separated)
    Returns None (after printing the error) if a slug/category/city is unknown.
    """
    if not run_args or run_args == ["all"]:
        return list(REGISTRY)

    if run_args[0].startswith(":"):
        city = run_args[0][1:]
        if not city:
            print("usage: cartelera run :<city_slug>", file=sys.stderr)
            return None
        slugs = _sources_in_city(city)
        if not slugs:
            known = sorted({
                v.city_slug for _s, source in REGISTRY.values() for v in source.venues
            })
            print(f"no sources in city {city!r}; known cities: {known}", file=sys.stderr)
            return None
        return slugs

    if run_args[0] in ("-c", "--category"):
        if len(run_args) < 2:
            print("usage: cartelera run -c <category_slug>", file=sys.stderr)
            return None
        category = run_args[1]
        slugs = _sources_in_category(category)
        if not slugs:
            known = sorted({
                c for _s, source in REGISTRY.values()
                for v in source.venues for c in v.category_slugs
            })
            print(f"no sources in category {category!r}; known categories: {known}", file=sys.stderr)
            return None
        return slugs

    # One or more explicit slugs, comma- and/or space-separated.
    slugs = [s for arg in run_args for s in arg.split(",") if s]
    unknown = [s for s in slugs if s not in REGISTRY]
    if unknown:
        print(f"unknown source slug(s) {unknown}; known: {sorted(REGISTRY)}", file=sys.stderr)
        return None
    return slugs


def _report(results: list[ScrapeResult]) -> None:
    for r in results:
        if r.verdict == health.HEALTHY:
            extra = f", {r.hidden} hidden" if r.hidden else ""
            print(f"[ok]   {r.source_slug}: {len(r.events)} events{extra}")
        elif r.verdict == health.DEGRADED:
            print(f"[DEGRADED] {r.source_slug}: {len(r.events)} events written, nothing hidden; "
                  + "; ".join(r.fired), file=sys.stderr)
        else:
            label = "SITE DOWN" if r.verdict == health.SITE_DOWN else "FAIL"
            print(f"[{label}] {r.source_slug}: {r.error}", file=sys.stderr)


def _dry_run(module_name: str) -> int:
    """Run a single scraper standalone — no DB, no seed, no upsert.

    Imports `cartelera.scrapers.<module_name>` (which runs its register(...) call),
    runs the scraper, and prints totals + per-field coverage so a scraper can be
    developed and verified in isolation from the shared dev database. Use this
    while authoring a new scraper; wire it into seed/run only once it's solid.
    """
    try:
        importlib.import_module(f"cartelera.scrapers.{module_name}")
    except ModuleNotFoundError as exc:
        print(f"no scraper module {module_name!r}: {exc}", file=sys.stderr)
        return 1
    # The module's register(...) keys the REGISTRY by source slug, which may
    # differ from the module name; take the entry it just added (last one
    # registered).
    if not REGISTRY:
        print(f"module {module_name!r} registered no scraper", file=sys.stderr)
        return 1
    # Find the entry whose scraper module matches; fall back to the sole/last one.
    slug, scraper = None, None
    for s_slug, (s, _) in REGISTRY.items():
        if type(s).__module__.endswith(f".{module_name}"):
            slug, scraper = s_slug, s
            break
    if scraper is None:
        slug, (scraper, _) = list(REGISTRY.items())[-1]

    try:
        events = scraper.scrape()
    except Exception as exc:  # noqa: BLE001 - report cleanly for the author
        print(f"[FAIL] {slug}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    _print_coverage(slug, events)
    return 0


def _print_coverage(source_slug: str, events: list[ScrapedEvent]) -> None:
    n = len(events)
    print(f"[dry-run] {source_slug}: {n} events")
    if not n:
        return
    pct = lambda c: f"{c}/{n} ({100 * c // n}%)"  # noqa: E731
    print(f"  with start_time:  {pct(sum(1 for e in events if e.start_time))}")
    print(f"  with price:       {pct(sum(1 for e in events if e.price))}")
    print(f"  with image_url:   {pct(sum(1 for e in events if e.image_url))}")
    print(f"  with annotations: {pct(sum(1 for e in events if e.annotations))}")
    print(f"  with external_id: {pct(sum(1 for e in events if e.external_id))}")
    cats: dict[str, int] = {}
    for e in events:
        for c in e.category_slugs:
            cats[c] = cats.get(c, 0) + 1
    print(f"  categories:       {cats}")
    dupes = len(events) - len({e.external_id for e in events if e.external_id})
    if dupes:
        print(f"  !! {dupes} duplicate external_id(s) — occurrences will collapse on upsert")
    print("  --- first 5 events ---")
    for e in events[:5]:
        t = e.start_time.strftime("%H:%M") if e.start_time else "--:--"
        print(f"  {e.start_date} {t} | {e.price or '-':>8} | {e.title[:60]}")


def main() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else "help"

    if cmd not in {"migrate", "seed", "run", "dry-run", "health"}:
        print(
            "usage: cartelera [migrate|seed|"
            "run [all|<slug>[,<slug>...]|:<city_slug>|-c <category_slug>]|"
            "dry-run <module_name>|"
            "health [ack <source>|rekey <source> [--apply]]]",
            file=sys.stderr,
        )
        return 1

    # dry-run is DB-free by design: run a scraper standalone without seed/upsert.
    if cmd == "dry-run":
        if len(args) < 2:
            print("usage: cartelera dry-run <module_name>", file=sys.stderr)
            return 1
        return _dry_run(args[1])

    if cmd == "migrate":
        # Create the target database first if it doesn't exist yet, so a fresh
        # checkout can `migrate` without a manual createdb.
        if ensure_database_exists():
            print("created database")
        engine = make_engine()
        applied = apply_migrations(engine)
        print(f"applied: {applied or 'none (up to date)'}")
        return 0

    # Both `seed` and `run` need the schema in place. Apply migrations first so
    # the command works against a fresh database without a separate `migrate`
    # step (migrations are idempotent, so this is a no-op when up to date).
    if ensure_database_exists():
        print("created database")
    engine = make_engine()
    apply_migrations(engine)

    session = make_session_factory()()
    try:
        if cmd == "seed":
            seed_db(session)
            print("seeded")
            return 0
        if cmd == "health":
            load_all()
            return health_ops.main(session, args[1:], make_tracker())
        # cmd == "run"
        seed_db(session)
        slugs = _resolve_run_targets(args[1:])
        if slugs is None:
            return 1
        tracker = make_tracker()
        results = [run_one(session, slug, tracker=tracker) for slug in slugs]
        _report(results)
        # Non-zero when any source's data could not be written (broken /
        # site_down). Degraded alone exits 0: its data was written and its
        # GitHub issue is the alert.
        return 0 if all(r.ok for r in results) else 1
    finally:
        session.close()
