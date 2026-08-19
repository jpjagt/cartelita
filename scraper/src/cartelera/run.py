from __future__ import annotations
import importlib
import logging
import sys
from decouple import config
from sqlalchemy.orm import Session
from cartelera.db import make_engine, make_session_factory, ensure_database_exists
from cartelera.migrate import apply_migrations
from cartelera.seed import seed as seed_db
from cartelera.upsert import upsert_venue_events
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


def run_one(session: Session, source_slug: str) -> ScrapeResult:
    """Scrape + upsert a single source in its own transaction.
    On any failure, roll back so the source's existing rows are left untouched."""
    scraper, source = REGISTRY[source_slug]
    try:
        events = scraper.scrape()
        for venue_slug, venue_events in _group_events_by_venue(source, events).items():
            upsert_venue_events(session, venue_slug, venue_events)
        session.commit()
        return ScrapeResult(source_slug=source_slug, ok=True, events=events)
    except Exception as exc:  # noqa: BLE001 - we want all failures isolated per source
        session.rollback()
        logger.exception("scrape failed for source %r", source_slug)
        return ScrapeResult(source_slug=source_slug, ok=False, error=f"{type(exc).__name__}: {exc}")


def run_all(session: Session) -> list[ScrapeResult]:
    return [run_one(session, slug) for slug in REGISTRY]


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
        if r.ok:
            print(f"[ok]   {r.source_slug}: {len(r.events)} events")
        else:
            print(f"[FAIL] {r.source_slug}: {r.error}", file=sys.stderr)


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


def _ig_login() -> int:
    """One-off bootstrap: log into Instagram by hand, store the session.

    Opens a *headed* Chromium (through IG_PROXY_URL, so the session is minted
    from the same exit IP the nightly capture will use) and waits for a human
    to log in — no form automation, because checkpoints and 2FA are precisely
    what an automated login fails at, and a human clears them in seconds. The
    resulting storage_state is persisted in Postgres and reused by every later
    capture run."""
    from cartelera.ig import archive as ig_archive
    from cartelera.ig.capture import login_interactively

    proxy_url = config("IG_PROXY_URL", default=None)
    print("Opening a browser window on instagram.com.")
    print("Log in manually as the scrape account (checkpoints/2FA included).")
    if proxy_url:
        print("Traffic goes through IG_PROXY_URL.")
    print("The window closes by itself once the session cookie appears.")
    try:
        state = login_interactively(proxy_url)
    except TimeoutError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    if ensure_database_exists():
        print("created database")
    engine = make_engine()
    apply_migrations(engine)
    session = make_session_factory()()
    try:
        ig_archive.set_session_state(session, state)
        session.commit()
    finally:
        session.close()
    print("saved Instagram session state")
    return 0


def main() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else "help"

    if cmd not in {"migrate", "seed", "run", "dry-run", "ig-login"}:
        print(
            "usage: cartelera [migrate|seed|"
            "run [all|<slug>[,<slug>...]|:<city_slug>|-c <category_slug>]|"
            "dry-run <module_name>|ig-login]",
            file=sys.stderr,
        )
        return 1

    if cmd == "ig-login":
        return _ig_login()

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
        # cmd == "run"
        seed_db(session)
        slugs = _resolve_run_targets(args[1:])
        if slugs is None:
            return 1
        results = [run_one(session, slug) for slug in slugs]
        _report(results)
        return 0 if all(r.ok for r in results) else 1
    finally:
        session.close()
