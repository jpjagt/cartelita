from __future__ import annotations
import datetime as dt
import importlib
import logging
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from cartelera import geocode, health
from cartelera.github import IssueTracker, make_tracker
from cartelera import health_ops
from cartelera.health_ops import sync_issue, sync_degraded_venues, module_of
from cartelera.discovery import accept_discovered, source_venue_slugs, sync_venue_review
from cartelera.models import ScrapeRun, Venue
from cartelera.db import make_engine, make_session_factory, ensure_database_exists
from cartelera.migrate import apply_migrations
from cartelera.seed import seed as seed_db, upsert_discovered_venue, extend_venue_categories
from cartelera.upsert import (
    upsert_venue_events, known_upcoming_snapshot, count_reseen, count_misses,
)
from cartelera.types import ScrapeResult, ScrapedEvent, SourceDefinition, VenueDefinition
from cartelera.scrapers import REGISTRY, load_all
from cartelera.scrapers.base import DiscoversVenues

logger = logging.getLogger(__name__)


def _group_events_by_venue(
    source: SourceDefinition, events: list[ScrapedEvent], discovered: Iterable[str] = ()
) -> dict[str, list[ScrapedEvent]]:
    """Resolve each event to one of the source's venues, failing fast on any
    mismatch. For a single-venue source, events may leave venue_slug unset (it
    resolves to the sole venue); a multi-venue source must set it on every
    event, and any slug outside the source's venue list — its editorial
    whitelist — plus, for an opt-out source, the `discovered` venue slugs, is
    an error, never a silent drop."""
    known = {v.slug for v in source.venues} | set(discovered)
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


@dataclass
class _Written:
    verdict: str
    fired: list[health.FiredRule]
    metrics: dict
    hidden: int
    new_venues: list[dict] = field(default_factory=list)
    degraded_venues: list[str] = field(default_factory=list)
    new_categories: list[dict] = field(default_factory=list)


def _extend_categories(
    session: Session, venues: dict[str, Venue], by_venue: dict[str, list[ScrapedEvent]],
    static: set[str],
) -> list[dict]:
    """For a source with `extends_venue_categories`: add to each of its
    code-defined venues the categories its events carry that the venue lacks
    (seed.extend_venue_categories). Returns the added pairs as
    {slug, name, category, events}. Discovered venues grow on their own
    (seed.upsert_discovered_venue) and aren't reported here."""
    added: list[dict] = []
    for slug in sorted(static & by_venue.keys()):
        venue = venues.get(slug)
        if venue is None:  # not seeded: the upsert raises its usual error
            continue
        evs = by_venue[slug]
        wanted = [c for ev in evs for c in ev.category_slugs]
        for c in extend_venue_categories(session, venue, wanted):
            added.append({"slug": slug, "name": venue.name, "category": c,
                          "events": sum(c in ev.category_slugs for ev in evs)})
    return added


def unlisted_categories(
    source: SourceDefinition, by_venue: dict[str, list[ScrapedEvent]]
) -> set[tuple[str, str]]:
    """(venue, category) pairs of a source's code-defined venues whose events
    no list shows: the venue's memberships are all whitelisted, and none to
    that category. Those events are stored but invisible until the venue's
    definition lists the category. (A source with `extends_venue_categories`
    fixes this itself at run time.)"""
    missing: set[tuple[str, str]] = set()
    for v in source.venues:
        if any(m.whitelist_category_slug is None for m in v.list_memberships):
            continue
        shown = {m.whitelist_category_slug for m in v.list_memberships}
        missing |= {(v.slug, c) for ev in by_venue.get(v.slug, [])
                    for c in ev.category_slugs if c not in shown}
    return missing


def _discover(
    session: Session, source: SourceDefinition, events: list[ScrapedEvent],
    discovered: list[VenueDefinition],
) -> tuple[list[ScrapedEvent], list[str], dict[str, str]]:
    """Create/grow the source's discovered venues (see cartelera.discovery).
    Returns (events minus those at refused venues, slugs created by this run,
    {refused slug: why})."""
    accepted, refused = accept_discovered(session, source, discovered)
    if refused:
        logger.warning("%s: skipped events at discovered venues it may not create "
                       "(deny or merge them in code): %s", source.slug, "; ".join(refused.values()))
        events = [ev for ev in events if ev.venue_slug not in refused]
    created = [d.slug for d in accepted if upsert_discovered_venue(session, source.slug, d)]
    return events, created, refused


def _write_source(
    session: Session, source: SourceDefinition, events: list[ScrapedEvent], today: dt.date,
    discovered: list[VenueDefinition] | None = None,
) -> _Written:
    """Classify a successful scrape and write it. Discovered venues (an
    opt-out source) are created first; metrics are taken from a pre-write
    snapshot; then upsert (healthy + degraded) and, only when healthy, count
    misses / hide. Raises on any write-side failure (caller rolls back)."""
    created: list[str] = []
    refused: dict[str, str] = {}
    if discovered:
        events, created, refused = _discover(session, source, events, discovered)
    slugs = source_venue_slugs(session, source)
    static = {v.slug for v in source.venues}
    by_venue = _group_events_by_venue(source, events, discovered=set(slugs) - static)
    venues = {v.slug: v for v in session.scalars(select(Venue).where(Venue.slug.in_(slugs)))}
    # A discovered venue absent from this run isn't evaluated on its own:
    # discovered venues are the feed's long tail (one-off gigs at a café), so
    # going quiet is normal — and it is what a deny/merge in code looks like.
    # Its known events still count toward the source's coverage and are
    # hidden by miss counting like any other.
    quiet = {s for s in slugs if s not in static and s not in by_venue}

    # 0. venue categories: an opted-in source extends its code-defined venues'
    # categories from its own (before the upsert, so the events are listed
    # right away); for any other source an unlisted category is only logged.
    new_categories: list[dict] = []
    if source.extends_venue_categories:
        new_categories = _extend_categories(session, venues, by_venue, static)
    elif missing := unlisted_categories(source, by_venue):
        logger.warning("%s: venues with events in categories no list shows them in "
                       "(add the category to the venue's definition): %s", source.slug,
                       ", ".join(f"{v}/{c}" for v, c in sorted(missing)))

    # 1. pre-write snapshot → metrics. Coverage is measured against what the
    # previous trusted run saw — per venue: the newest run trusted for THAT
    # venue (healthy and the venue not degraded in it, or acked; see
    # health.RunView.venue_trusted); none yet → coverage skipped. Degraded
    # runs don't move the reference: otherwise a persistently truncated
    # scraper (or venue) would be flagged once, then measured against its own
    # truncated view, score healthy, and hide the real events through miss
    # counting.
    trusted = _trusted_runs(session, source.slug)
    venue_metrics: dict[str, health.ScopeMetrics] = {}
    for slug in slugs:
        evs = by_venue.get(slug, [])
        venue = venues.get(slug)
        if venue is None:
            if evs:  # let the upsert raise its usual error
                upsert_venue_events(session, slug, evs)
            continue
        idx = known_upcoming_snapshot(
            session, venue.id, today, health.venue_reference(trusted, slug))
        venue_metrics[slug] = health.compute_metrics(
            evs, len(idx.ids), count_reseen(idx, evs), today)
    metrics = health.RunMetrics(
        source=health.aggregate_metrics(venue_metrics.values()),
        venues={s: m for s, m in venue_metrics.items() if s not in quiet})

    # 2. baseline + rules → source verdict (source-level rules only) and the
    # venues degraded on their own (venue-level rules of a multi-venue source)
    fired = health.evaluate_run(
        metrics, health.source_history(trusted),
        {s: health.venue_history(trusted, s) for s in metrics.venues})
    verdict = health.verdict_for(fired)
    degraded_venues = sorted(health.venue_rules(fired))

    # 3. write; 4. hide (healthy source only, and never at a degraded venue:
    # its events are neither missed nor hidden this run)
    seen: set[int] = set()
    for slug, evs in by_venue.items():
        upsert_venue_events(session, slug, evs, seen_ids=seen)
    hidden = 0
    if verdict == health.HEALTHY:
        for slug, venue in venues.items():
            if slug not in degraded_venues:
                hidden += count_misses(session, venue.id, seen, today)[1]
    metrics_json = metrics.to_json(fired)
    new_venues = [
        {"slug": s, "name": venues[s].name, "address": venues[s].address,
         "categories": [c.slug for c in venues[s].categories],
         "events": len(by_venue.get(s, []))}
        for s in created
    ]
    if new_venues:
        metrics_json["new_venues"] = new_venues
    if refused:
        metrics_json["refused_venues"] = refused
    if new_categories:
        metrics_json["new_categories"] = new_categories
    return _Written(verdict, fired, metrics_json, hidden, new_venues, degraded_venues,
                    new_categories)


def _trusted_runs(session: Session, source_slug: str) -> list[health.RunView]:
    """The source's recent runs that can serve as a baseline / coverage
    reference for the source or any of its venues (healthy, acked, or holding
    a venue ack), newest first. Per-scope filtering happens in health
    (source_history / venue_history / venue_reference)."""
    rows = session.scalars(
        select(ScrapeRun)
        .where(ScrapeRun.source_slug == source_slug,
               ScrapeRun.metrics.is_not(None),
               or_(ScrapeRun.verdict == health.HEALTHY, ScrapeRun.acked.is_(True),
                   ScrapeRun.metrics.has_key("acked_venues")))
        .order_by(ScrapeRun.started_at.desc(), ScrapeRun.id.desc())
        .limit(health.BASELINE_SCAN_RUNS)
    ).all()
    return [health_ops.view(r) for r in rows]


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
    data; degraded runs upsert but never count misses or hide. A venue of a
    multi-venue source degraded on its own leaves the source healthy, but its
    events are neither missed nor hidden this run. Venues an
    opt-out source discovered are created inside that transaction, as are the
    categories a source with `extends_venue_categories` adds to its venues;
    the venues and categories new this run go to the source's review issue
    (see cartelera.discovery)."""
    scraper, source = REGISTRY[source_slug]
    today = today or dt.date.today()
    started = _now()
    events: list[ScrapedEvent] = []
    fired: list[health.FiredRule] = []
    metrics_json: dict | None = None
    error_kind = error_message = None
    hidden = 0
    new_venues: list[dict] = []
    degraded_venues: list[str] = []
    new_categories: list[dict] = []
    try:
        events = scraper.scrape()
        discovered = (scraper.discovered_venues()
                      if isinstance(scraper, DiscoversVenues) else None)
        w = _write_source(session, source, events, today, discovered)
        verdict, fired, metrics_json, hidden = w.verdict, w.fired, w.metrics, w.hidden
        new_venues, degraded_venues, new_categories = (
            w.new_venues, w.degraded_venues, w.new_categories)
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

    if new_venues or new_categories:
        try:
            sync_venue_review(session, source_slug, module_of(source_slug), new_venues,
                              tracker or make_tracker(), today=today,
                              new_categories=new_categories)
        except Exception:  # noqa: BLE001 - GitHub trouble must never fail the scrape
            session.rollback()
            logger.exception("posting new venues for review failed for source %r", source_slug)

    if metrics_json is not None:
        try:
            sync_degraded_venues(session, source_slug, tracker or make_tracker())
        except Exception:  # noqa: BLE001 - GitHub trouble must never fail the scrape
            session.rollback()
            logger.exception("posting degraded venues for review failed for source %r",
                             source_slug)

    return ScrapeResult(
        source_slug=source_slug,
        ok=verdict not in health.FAILED_VERDICTS,
        events=events,
        error=error,
        verdict=verdict,
        fired=[r.detail if r.scope == "source" else f"{r.scope}: {r.detail}" for r in fired],
        hidden=hidden,
        new_venues=new_venues,
        degraded_venues=degraded_venues,
        new_categories=new_categories,
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
            if r.degraded_venues:
                print(f"       {r.source_slug}: {len(r.degraded_venues)} venue(s) degraded "
                      "(their events kept, none hidden): " + "; ".join(
                          f for f in r.fired if f.startswith("venue:")), file=sys.stderr)
        elif r.verdict == health.DEGRADED:
            print(f"[DEGRADED] {r.source_slug}: {len(r.events)} events written, nothing hidden; "
                  + "; ".join(r.fired), file=sys.stderr)
        else:
            label = "SITE DOWN" if r.verdict == health.SITE_DOWN else "FAIL"
            print(f"[{label}] {r.source_slug}: {r.error}", file=sys.stderr)
        if r.new_venues:
            print(f"       {r.source_slug}: {len(r.new_venues)} new venue(s), posted for review:")
            for v in r.new_venues:
                print(f"         + {v['name']} ({v['slug']}) — {v.get('address') or 'no address'}; "
                      f"{', '.join(v['categories'])}; {v['events']} events")
        if r.new_categories:
            print(f"       {r.source_slug}: {len(r.new_categories)} new venue categor"
                  f"{'y' if len(r.new_categories) == 1 else 'ies'}, posted for review:")
            for c in r.new_categories:
                print(f"         + {c['name']} ({c['slug']}) → {c['category']}; "
                      f"{c['events']} events")


# Venues `cartelera run` geocodes afterwards, at most: new (discovered or
# freshly defined) venues get coordinates the same night, and a backlog
# (e.g. a first deploy) drains over several nights instead of stretching the
# run. ~3 Nominatim requests a venue at 1/s → a few minutes at most.
GEOCODE_AFTER_RUN_MAX = 50


def _geocode_after_run(session: Session) -> None:
    """Geocode pending venues after a run — bounded and non-fatal: a failure
    is logged and never affects the run's exit code or health verdicts."""
    try:
        report = geocode.geocode_venues(session, max_venues=GEOCODE_AFTER_RUN_MAX)
    except Exception:  # noqa: BLE001 - geocoding must never fail the run
        session.rollback()
        logger.exception("geocoding venues after the run failed")
        return
    if report.hits or report.misses:
        left = f", {report.skipped} left for the next run" if report.skipped else ""
        print(f"[geocode] {len(report.hits)} venue(s) located, {len(report.misses)} "
              f"not found{left}")
        for city, slug, name in report.misses:
            print(f"         - {city}/{slug}: {name}")


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
    if isinstance(scraper, DiscoversVenues) and (found := scraper.discovered_venues()):
        print(f"  --- {len(found)} discovered venue(s) (created on `run` unless already known) ---")
        for v in found:
            print(f"  {v.slug}: {v.name} | {v.address or '-'} | {', '.join(v.category_slugs)}")
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

    if cmd not in {"migrate", "seed", "run", "dry-run", "health", "geocode"}:
        print(
            "usage: cartelera [migrate|seed|"
            "run [all|<slug>[,<slug>...]|:<city_slug>|-c <category_slug>]|"
            "dry-run <module_name>|"
            "health [<source>|ack <source> [<venue>]|rekey <source> [--apply]]|"
            "geocode [--city <slug>] [--force]]",
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
        if cmd == "geocode":
            return geocode.main(session, args[1:])
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
        _geocode_after_run(session)
        # Non-zero when any source's data could not be written (broken /
        # site_down). Degraded alone exits 0: its data was written and its
        # GitHub issue is the alert.
        return 0 if all(r.ok for r in results) else 1
    finally:
        session.close()
