from __future__ import annotations
import datetime as dt
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from cartelera.models import Venue, Event, Category, EventTranslation
from cartelera.types import ScrapedEvent
from cartelera.health import HIDE_AFTER_MISSES

# Optional fields a scrape may return empty; an empty value never overwrites a
# stored one (the null guard). start_time(s) and annotations are guarded too.
_GUARDED_FIELDS = (
    "end_date", "end_time", "price", "description", "image_url",
    "recurrence_hint", "language",
)


def _empty(v) -> bool:
    return v is None or v == "" or v == []


def _keep_or_set(obj, attr: str, value) -> None:
    """Null guard: set `attr` unless `value` is empty and a value is stored."""
    if _empty(value) and not _empty(getattr(obj, attr, None)):
        return
    setattr(obj, attr, value)


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


def upsert_venue_events(
    session: Session, venue_slug: str, scraped: list[ScrapedEvent],
    seen_ids: set[int] | None = None,
) -> int:
    """Upsert all scraped events for one venue. Returns number of rows written;
    when `seen_ids` is given, the written events' ids are added to it.
    Runs in the caller's transaction; caller commits/rolls back."""
    venue = session.scalars(select(Venue).where(Venue.slug == venue_slug)).one()
    cat_by_slug = {c.slug: c for c in session.scalars(select(Category)).all()}
    # Guard: external_id is the authoritative per-OCCURRENCE dedup key, so two
    # scraped events in one batch sharing one would silently overwrite each other
    # (e.g. a venue keying on a film slug that screens many times — qualify the id
    # with date+time). Fail loudly rather than collapse occurrences.
    batch_ids: dict[str, ScrapedEvent] = {}
    for se in scraped:
        if se.external_id is None:
            continue
        clash = batch_ids.get(se.external_id)
        if clash is not None:
            raise ValueError(
                f"duplicate external_id {se.external_id!r} within one scrape of "
                f"venue {venue_slug!r}: {clash.title!r} ({clash.start_date} "
                f"{clash.start_time}) and {se.title!r} ({se.start_date} "
                f"{se.start_time}). external_id must be unique per occurrence; "
                "qualify it with date/time if the venue's id is coarser."
            )
        batch_ids[se.external_id] = se
    written = 0
    touched: list[Event] = []
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
        now = dt.datetime.now(dt.timezone.utc)
        ev.title = se.title
        ev.start_date = se.start_date
        ev.source_url = se.source_url
        ev.external_id = se.external_id
        # Null guard: a run can change a value, never blank it. A field the
        # scrape returns as None/empty keeps the stored value (a dying selector
        # must not wipe known prices/times/descriptions).
        if se.start_times or se.start_time is not None or ev.start_time is None:
            ev.start_times = list(se.start_times)
            # start_time is the earliest session (ordering key); fall back to the
            # scalar the scraper set when no per-session list was provided.
            ev.start_time = min(se.start_times) if se.start_times else se.start_time
        for f in _GUARDED_FIELDS:
            _keep_or_set(ev, f, getattr(se, f))
        _keep_or_set(ev, "annotations", list(se.annotations))
        ev.scraped_at = now
        # Liveness: seen now; a hidden event that reappears is visible again.
        ev.last_seen_at = now
        ev.missed_runs = 0
        ev.hidden_at = None
        ev.categories = cats
        _reconcile_translations(ev, se)
        touched.append(ev)
        written += 1
    session.flush()
    if seen_ids is not None:
        seen_ids.update(ev.id for ev in touched)
    return written


def _reconcile_translations(ev: Event, se: ScrapedEvent) -> None:
    """Reconcile translations in place, keyed by lang. We do NOT reassign the
    whole collection: replacing it makes the cascade DELETE the old rows and
    INSERT brand-new ones for the same (event_id, lang) keys, and a mid-loop
    autoflush (triggered by the next event's _find_existing SELECT) can flush
    those INSERTs before the orphan DELETEs land — colliding on the
    (event_id, lang) unique constraint (the Liceu failure: many sessions of
    one production sharing es/en). Updating matching langs in place and only
    adding/removing the genuine diff avoids any same-key delete+insert churn.

    Null guard: a scrape with no translations at all keeps the stored ones
    (the extra-language fetch may have failed), and a None description /
    source_url keeps the stored value."""
    if not se.translations:
        return
    by_lang = {t.lang: t for t in ev.translations}
    scraped_langs = {t.lang for t in se.translations}
    for t in se.translations:
        row = by_lang.get(t.lang)
        if row is None:
            ev.translations.append(EventTranslation(
                lang=t.lang, title=t.title,
                description=t.description, source_url=t.source_url))
        else:
            row.title = t.title
            _keep_or_set(row, "description", t.description)
            _keep_or_set(row, "source_url", t.source_url)
    for lang, row in by_lang.items():
        if lang not in scraped_langs:
            ev.translations.remove(row)


def count_misses(
    session: Session, venue_id: int, seen_ids: set[int], today: dt.date,
    now: dt.datetime | None = None,
) -> tuple[int, int]:
    """After a HEALTHY run: the venue's visible upcoming events the run did not
    return get missed_runs += 1, and are hidden once it reaches
    HIDE_AFTER_MISSES. Past events are never touched; nothing is deleted.
    Returns (missed, newly_hidden)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    cond = [Event.venue_id == venue_id, Event.start_date >= today, Event.hidden_at.is_(None)]
    if seen_ids:
        cond.append(Event.id.not_in(seen_ids))
    missed = session.execute(
        update(Event).where(*cond)
        .values(missed_runs=Event.missed_runs + 1)
        .returning(Event.id, Event.missed_runs)
        .execution_options(synchronize_session=False)
    ).all()
    to_hide = [eid for eid, n in missed if n >= HIDE_AFTER_MISSES]
    if to_hide:
        session.execute(
            update(Event).where(Event.id.in_(to_hide)).values(hidden_at=now)
            .execution_options(synchronize_session=False))
    session.expire_all()
    return len(missed), len(to_hide)


# --- pre-write matching (health metrics) --------------------------------------

class MatchIndex:
    """In-memory mirror of _find_existing's dedup tiers over a set of stored
    events, used to count how many known upcoming events a run re-sees
    without writing anything."""

    def __init__(self, rows: list[tuple[int, str | None, str, str, dt.date]]):
        # rows: (id, external_id, source_url, title, start_date)
        self.ids: set[int] = {r[0] for r in rows}
        self.by_ext: dict[str, int] = {}
        self.by_url: dict[str, int] = {}
        self.by_title_date: dict[tuple[str, dt.date], int] = {}
        for eid, ext, url, title, start in rows:
            if ext is not None:
                self.by_ext.setdefault(ext, eid)
            self.by_url.setdefault(url, eid)
            self.by_title_date.setdefault((title, start), eid)

    def match(self, se: ScrapedEvent) -> int | None:
        if se.external_id is not None:
            return self.by_ext.get(se.external_id)
        return self.by_url.get(se.source_url) or self.by_title_date.get((se.title, se.start_date))


def known_upcoming_snapshot(
    session: Session, venue_id: int, today: dt.date, seen_since: dt.datetime | None
) -> MatchIndex:
    """The coverage denominator, before this run writes anything: the venue's
    visible upcoming events that the source's previous trusted (healthy or
    acked) run saw (last_seen_at >= its start). Rows nobody has re-seen since (stale rows
    from before scraper health, long gone from the site) are excluded — they
    age out through miss counting instead of pinning coverage low forever.
    No previous trusted run (`seen_since` None) → empty: coverage is
    skipped for this run."""
    if seen_since is None:
        return MatchIndex([])
    rows = session.execute(
        select(Event.id, Event.external_id, Event.source_url, Event.title, Event.start_date)
        .where(Event.venue_id == venue_id, Event.start_date >= today, Event.hidden_at.is_(None),
               Event.last_seen_at >= seen_since)
    ).all()
    return MatchIndex([tuple(r) for r in rows])


def count_reseen(index: MatchIndex, scraped: list[ScrapedEvent]) -> int:
    return len({eid for se in scraped if (eid := index.match(se)) is not None})
