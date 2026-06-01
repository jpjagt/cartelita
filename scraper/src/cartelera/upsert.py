from __future__ import annotations
import datetime as dt
from sqlalchemy import select
from sqlalchemy.orm import Session
from cartelera.models import Venue, Event, Category, EventTranslation
from cartelera.types import ScrapedEvent


def _find_existing(session: Session, venue_id: int, se: ScrapedEvent) -> Event | None:
    """Apply the dedup-key tiers in priority order.

    Tiers 2 (source_url) and 3 (title + start_date) are best-effort fallbacks
    for scrapers that cannot supply a stable external_id.  Tier 2 is only
    reliable when the scraper emits a *per-event* URL — a shared listing URL
    reused across many events will cause false matches.  Prefer supplying
    external_id or a per-event source_url wherever possible.
    """
    if se.external_id is not None:
        e = session.scalars(select(Event).where(
            Event.venue_id == venue_id, Event.external_id == se.external_id)).first()
        if e:
            return e
        return None  # external_id tier is authoritative when present
    # tier 2: (venue_id, source_url)
    e = session.scalars(select(Event).where(
        Event.venue_id == venue_id, Event.source_url == se.source_url)).first()
    if e:
        return e
    # tier 3: (venue_id, title, start_date)
    return session.scalars(select(Event).where(
        Event.venue_id == venue_id, Event.title == se.title,
        Event.start_date == se.start_date)).first()


def upsert_venue_events(session: Session, venue_slug: str, scraped: list[ScrapedEvent]) -> int:
    """Upsert all scraped events for one venue. Returns number of rows written.
    Runs in the caller's transaction; caller commits/rolls back."""
    venue = session.scalars(select(Venue).where(Venue.slug == venue_slug)).one()
    cat_by_slug = {c.slug: c for c in session.scalars(select(Category)).all()}
    written = 0
    for se in scraped:
        try:
            cats = [cat_by_slug[s] for s in se.category_slugs]
        except KeyError as exc:
            raise ValueError(
                f"unknown category slug {exc.args[0]!r} for venue {venue_slug!r}; "
                "seed the category before scraping"
            ) from exc
        existing = _find_existing(session, venue.id, se)
        if existing:
            ev = existing
        else:
            ev = Event(venue_id=venue.id)
            session.add(ev)
        ev.title = se.title
        ev.start_date = se.start_date
        ev.start_time = se.start_time
        ev.end_date = se.end_date
        ev.end_time = se.end_time
        ev.price = se.price
        ev.description = se.description
        ev.image_url = se.image_url
        ev.source_url = se.source_url
        ev.external_id = se.external_id
        ev.recurrence_hint = se.recurrence_hint
        ev.annotations = list(se.annotations)
        ev.scraped_at = dt.datetime.now(dt.timezone.utc)
        ev.categories = cats
        # Replace translations wholesale (canonical content lives on the event).
        ev.translations = [
            EventTranslation(lang=t.lang, title=t.title,
                             description=t.description, source_url=t.source_url)
            for t in se.translations
        ]
        written += 1
    session.flush()
    return written
