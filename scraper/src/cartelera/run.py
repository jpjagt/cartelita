from __future__ import annotations
import importlib
import logging
import sys
from sqlalchemy.orm import Session
from cartelera.db import make_engine, make_session_factory, ensure_database_exists
from cartelera.migrate import apply_migrations
from cartelera.seed import seed as seed_db
from cartelera.upsert import upsert_venue_events
from cartelera.types import ScrapeResult, ScrapedEvent
from cartelera.scrapers import REGISTRY, load_all

logger = logging.getLogger(__name__)


def run_one(session: Session, venue_slug: str) -> ScrapeResult:
    """Scrape + upsert a single venue in its own transaction.
    On any failure, roll back so the venue's existing rows are left untouched."""
    scraper, _ = REGISTRY[venue_slug]
    try:
        events = scraper.scrape()
        upsert_venue_events(session, venue_slug, events)
        session.commit()
        return ScrapeResult(venue_slug=venue_slug, ok=True, events=events)
    except Exception as exc:  # noqa: BLE001 - we want all failures isolated per venue
        session.rollback()
        logger.exception("scrape failed for venue %r", venue_slug)
        return ScrapeResult(venue_slug=venue_slug, ok=False, error=f"{type(exc).__name__}: {exc}")


def run_all(session: Session) -> list[ScrapeResult]:
    return [run_one(session, slug) for slug in REGISTRY]


def _venues_in_category(category_slug: str) -> list[str]:
    """Registered venue slugs whose VenueDefinition lists `category_slug`."""
    return [
        slug for slug, (_scraper, venue) in REGISTRY.items()
        if category_slug in venue.category_slugs
    ]


def _resolve_run_targets(run_args: list[str]) -> list[str] | None:
    """Turn the `run` args into the ordered list of venue slugs to scrape.

    Forms:
      (none) / all        -> every registered venue
      -c <category_slug>  -> every venue whose definition has that category
      <slug>[,<slug>...]  -> the listed venues (comma- or space-separated)
    Returns None (after printing the error) if a slug/category is unknown.
    """
    if not run_args or run_args == ["all"]:
        return list(REGISTRY)

    if run_args[0] in ("-c", "--category"):
        if len(run_args) < 2:
            print("usage: cartelera run -c <category_slug>", file=sys.stderr)
            return None
        category = run_args[1]
        slugs = _venues_in_category(category)
        if not slugs:
            known = sorted({c for _s, v in REGISTRY.values() for c in v.category_slugs})
            print(f"no venues in category {category!r}; known categories: {known}", file=sys.stderr)
            return None
        return slugs

    # One or more explicit slugs, comma- and/or space-separated.
    slugs = [s for arg in run_args for s in arg.split(",") if s]
    unknown = [s for s in slugs if s not in REGISTRY]
    if unknown:
        print(f"unknown venue slug(s) {unknown}; known: {sorted(REGISTRY)}", file=sys.stderr)
        return None
    return slugs


def _report(results: list[ScrapeResult]) -> None:
    for r in results:
        if r.ok:
            print(f"[ok]   {r.venue_slug}: {len(r.events)} events")
        else:
            print(f"[FAIL] {r.venue_slug}: {r.error}", file=sys.stderr)


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
    # The module's register(...) keys the REGISTRY by venue_slug, which may differ
    # from the module name; take the entry it just added (last one registered).
    if not REGISTRY:
        print(f"module {module_name!r} registered no scraper", file=sys.stderr)
        return 1
    # Find the scraper whose module matches; fall back to the sole/last entry.
    scraper = None
    for s, _ in REGISTRY.values():
        if type(s).__module__.endswith(f".{module_name}"):
            scraper = s
            break
    if scraper is None:
        scraper = list(REGISTRY.values())[-1][0]

    try:
        events = scraper.scrape()
    except Exception as exc:  # noqa: BLE001 - report cleanly for the author
        print(f"[FAIL] {scraper.venue_slug}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    _print_coverage(scraper.venue_slug, events)
    return 0


def _print_coverage(venue_slug: str, events: list[ScrapedEvent]) -> None:
    n = len(events)
    print(f"[dry-run] {venue_slug}: {n} events")
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

    if cmd not in {"migrate", "seed", "run", "dry-run"}:
        print(
            "usage: cartelera [migrate|seed|"
            "run [all|<slug>[,<slug>...]|-c <category_slug>]|"
            "dry-run <module_name>]",
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
