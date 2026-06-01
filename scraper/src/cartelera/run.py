from __future__ import annotations
import logging
import sys
from sqlalchemy.orm import Session
from cartelera.db import make_engine, make_session_factory
from cartelera.migrate import apply_migrations
from cartelera.seed import seed as seed_db
from cartelera.upsert import upsert_venue_events
from cartelera.types import ScrapeResult
from cartelera.scrapers import REGISTRY
import cartelera.scrapers.jamboree  # noqa: F401  (registers the scraper)

logger = logging.getLogger(__name__)


def run_one(session: Session, venue_slug: str) -> ScrapeResult:
    """Scrape + upsert a single venue in its own transaction.
    On any failure, roll back so the venue's existing rows are left untouched."""
    scraper = REGISTRY[venue_slug]
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


def _report(results: list[ScrapeResult]) -> None:
    for r in results:
        if r.ok:
            print(f"[ok]   {r.venue_slug}: {len(r.events)} events")
        else:
            print(f"[FAIL] {r.venue_slug}: {r.error}", file=sys.stderr)


def main() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else "help"

    if cmd not in {"migrate", "seed", "run"}:
        print("usage: cartelera [migrate|seed|run [all|<venue_slug>]]", file=sys.stderr)
        return 1

    engine = make_engine()
    if cmd == "migrate":
        applied = apply_migrations(engine)
        print(f"applied: {applied or 'none (up to date)'}")
        return 0

    session = make_session_factory()()
    try:
        if cmd == "seed":
            seed_db(session)
            print("seeded")
            return 0
        # cmd == "run"
        target = args[1] if len(args) > 1 else "all"
        if target != "all" and target not in REGISTRY:
            print(f"unknown venue slug {target!r}; known: {sorted(REGISTRY)}", file=sys.stderr)
            return 1
        results = run_all(session) if target == "all" else [run_one(session, target)]
        _report(results)
        return 0 if all(r.ok for r in results) else 1
    finally:
        session.close()
