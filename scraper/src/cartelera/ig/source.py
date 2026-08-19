"""The IG source: an ordinary Cartelera scraper over an Instagram profile.

`IgProfileScraper.scrape()` is the whole nightly pipeline for one profile, in
three phases that are deliberately independent of each other:

1. **Capture** — new posts of the handle into the archive (append-only).
   Failures propagate: the runner isolates and reports per-source failures,
   and an honest failure is what marks the venue stale instead of quietly
   publishing yesterday's programme.
2. **Extract** — one vision-LLM call per not-yet-parsed archived post,
   committed per post so a bad post costs only itself. A post that fails is
   logged and left extraction-less, which *is* its retry: the next run picks
   it up again. Only an all-fail sweep raises (the provider is down).
3. **Emit** — read the *whole* archive, gate every stored extraction against
   today, and map what survives to `ScrapedEvent`s. Emission is a pure
   re-read: it never re-parses, so gate rules and the calendar can move
   without touching a single stored extraction.

Whitelist semantics live here, not in the gate: an event naming a venue
outside the source's roster, or a category outside that venue's, is dropped
and logged. A model must never be able to crash the source through the
runner's fail-fast or the upsert's unknown-category check.

This module orchestrates through capture.py/extract.py only — no Playwright,
no litellm imports (both are heavy, and only one of the three phases needs
each).
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from decouple import config as env
from sqlalchemy.orm import Session

from cartelera.ig.archive import (
    archived_shortcodes,
    extracted_posts,
    get_session_state,
    posts_missing_extraction,
    save_extraction,
    set_session_state,
    upsert_posts,
)
from cartelera.ig.capture import capture_new_posts
from cartelera.ig.extract import (
    PROMPT_VERSION,
    ExtractedContent,
    GatedEvent,
    confidence_threshold,
    extract_model,
    extract_post,
    gate_events,
)
from cartelera.ig.types import RosterVenue
from cartelera.models import IgPost
from cartelera.types import (
    ScrapedEvent,
    ScrapedTranslation,
    SourceDefinition,
    VenueDefinition,
)

logger = logging.getLogger(__name__)

POST_URL = "https://www.instagram.com/p/{shortcode}/"
DEFAULT_TZ = "Asia/Yerevan"


@dataclass
class IgSourceConfig:
    """Everything that differs between one IG source and the next.

    A thin scraper module is just one of these plus a `register(...)` call:
    which handle to read, which venues it may emit for (the source definition
    doubles as the editorial whitelist), what to tell the model about each
    venue, and which extracted language is the canonical event content for
    this city (the rest become translations)."""
    handle: str
    source: SourceDefinition
    canonical_lang: str
    hints_by_venue: dict[str, str | None] = field(default_factory=dict)
    tz: str = DEFAULT_TZ  # the venue's timezone: emission's notion of "today"
    limit_per_profile: int = 12


def _today(tz: str) -> dt.date:
    """Today in the venue's own timezone — never the server's."""
    return dt.datetime.now(ZoneInfo(tz)).date()


def _proxy_url() -> str | None:
    """Read like `cartelera ig-login` does: capture must leave from the same
    exit IP the session was minted on."""
    return env("IG_PROXY_URL", default=None)


class IgProfileScraper:
    """The `Scraper` contract over one Instagram profile."""

    def __init__(self, config: IgSourceConfig, session_factory=None):
        self.config = config
        # Resolved at scrape time (not import time) so importing a scraper
        # module never needs a database; tests inject a factory on the test
        # engine.
        self._session_factory = session_factory
        if len(config.source.venues) == 1:
            # The single-venue convention other scrapers follow.
            self.venue_slug = config.source.venues[0].slug

    # -- plumbing ---------------------------------------------------------

    @property
    def _slug(self) -> str:
        return self.config.source.slug

    def _session(self) -> Session:
        factory = self._session_factory
        if factory is None:
            from cartelera.db import make_session_factory

            factory = make_session_factory()
        return factory()

    def _roster(self) -> list[RosterVenue]:
        return [
            RosterVenue(
                slug=venue.slug,
                name=venue.name,
                category_slugs=list(venue.category_slugs),
                hints=self.config.hints_by_venue.get(venue.slug),
            )
            for venue in self.config.source.venues
        ]

    # -- the three phases -------------------------------------------------

    def scrape(self) -> list[ScrapedEvent]:
        session = self._session()
        try:
            self._capture(session)
            self._extract(session)
            return self._emit(session)
        finally:
            session.close()

    def _capture(self, session: Session) -> None:
        """Archive the handle's new posts. Never swallows a failure.

        Also re-persists `storage_state`: IG rotates session cookies over the
        course of a run, and `capture_new_posts` only returns at all when the
        whole call succeeded (no `IgSessionInvalid`), so reaching this point
        is exactly the "successful run" condition for saving the refresh."""
        state = get_session_state(session)
        if state is None:
            raise RuntimeError(
                f"no stored Instagram session, so {self._slug!r} cannot capture; "
                "run `cartelera ig-login` once to mint one"
            )
        known = archived_shortcodes(session, self.config.handle)
        result = capture_new_posts(
            [(self.config.handle, known)],
            state,
            _proxy_url(),
            limit_per_profile=self.config.limit_per_profile,
        )
        posts = result.posts.get(self.config.handle, [])
        inserted = upsert_posts(session, self._slug, posts)
        set_session_state(session, result.storage_state)
        session.commit()
        logger.info("%s: captured %d post(s), %d newly archived", self._slug, len(posts), inserted)

    def _extract(self, session: Session) -> None:
        """One LLM call per unparsed post, committed post by post."""
        pending = posts_missing_extraction(session, self._slug)
        if not pending:
            return
        roster = self._roster()
        model = extract_model()
        failed = 0
        for post in pending:
            try:
                extraction = extract_post(post, roster, model)
                save_extraction(session, post.shortcode, extraction, model, PROMPT_VERSION)
                session.commit()
            except Exception as exc:  # noqa: BLE001 - one bad post must cost only itself
                session.rollback()
                failed += 1
                logger.warning(
                    "%s: extraction failed for %s (%s); it stays unparsed and retries next run",
                    self._slug, post.shortcode, exc,
                )
        if failed == len(pending):
            raise RuntimeError(
                f"{self._slug}: extraction failed for all {failed} unparsed post(s) "
                f"with model {model!r} — the provider is likely down"
            )
        logger.info("%s: extracted %d/%d post(s)", self._slug, len(pending) - failed, len(pending))

    def _emit(self, session: Session) -> list[ScrapedEvent]:
        """Re-read the whole archive and publish what today's gate allows."""
        today = _today(self.config.tz)
        threshold = confidence_threshold()
        events: list[ScrapedEvent] = []
        for post in extracted_posts(session, self._slug):
            extraction = post.extraction or {}
            stored = len(extraction.get("events") or [])
            gated = gate_events(
                extraction, today, threshold, label=f"{self._slug} {post.shortcode}"
            )
            for gate in gated:
                event = self._to_event(post, gate, stored)
                if event is not None:
                    events.append(event)
        logger.info("%s: emitting %d event(s) as of %s", self._slug, len(events), today)
        return events

    # -- mapping ----------------------------------------------------------

    def _to_event(self, post: IgPost, gate: GatedEvent, stored: int) -> ScrapedEvent | None:
        """One gated event as a ScrapedEvent, or None if it fails the whitelist."""
        venue = self._resolve_venue(post.shortcode, gate)
        if venue is None:
            return None
        if gate.category not in venue.category_slugs:
            logger.info(
                "%s %s: drop event %d: category %r is not among %s's categories %s",
                self._slug, post.shortcode, gate.index, gate.category,
                venue.slug, venue.category_slugs,
            )
            return None

        source_url = POST_URL.format(shortcode=post.shortcode)
        canonical, translations = self._split_contents(gate, source_url)
        title = canonical.title.strip()
        if not title:
            # The schema demands a title but cannot demand a non-empty one; an
            # untitled event is a blank card on the site, so drop it here.
            logger.info(
                "%s %s: drop event %d: no title in the %r content",
                self._slug, post.shortcode, gate.index, canonical.lang,
            )
            return None
        return ScrapedEvent(
            title=title,
            description=canonical.description,
            start_date=gate.date,
            start_time=gate.time,
            start_times=[gate.time] if gate.time else [],
            source_url=source_url,
            category_slugs=[gate.category],
            price=gate.price,
            language=gate.language,
            image_url=post.images[0].url if post.images else None,
            external_id=self._external_id(post.shortcode, gate.index, stored),
            venue_slug=gate.venue_slug,
            translations=translations,
        )

    def _resolve_venue(self, shortcode: str, gate: GatedEvent) -> VenueDefinition | None:
        """The source's venue this event belongs to; None means "drop it".

        The source's venue list is its editorial whitelist, exactly as for an
        aggregator — except that here the "aggregator" is a language model, so
        an off-roster attribution is dropped and logged rather than allowed to
        reach the runner's fail-fast and take the whole source down."""
        venues = self.config.source.venues
        if gate.venue_slug is None:
            if len(venues) == 1:
                return venues[0]
            logger.info(
                "%s %s: drop event %d: no venue_slug, and the source has %d venues",
                self._slug, shortcode, gate.index, len(venues),
            )
            return None
        for venue in venues:
            if venue.slug == gate.venue_slug:
                return venue
        logger.info(
            "%s %s: drop event %d: venue %r is not among the source's venues %s",
            self._slug, shortcode, gate.index, gate.venue_slug,
            sorted(v.slug for v in venues),
        )
        return None

    def _split_contents(
        self, gate: GatedEvent, source_url: str
    ) -> tuple[ExtractedContent, list[ScrapedTranslation]]:
        """Canonical content + one translation per other language.

        The canonical variant is the city's default locale when the post
        carries it, else the first one the model read — this is extraction,
        not translation, so there is no fallback to invent. Repeated languages
        collapse to their first entry: EventTranslation is one row per lang."""
        contents = list(gate.contents)
        canonical = next(
            (c for c in contents if c.lang == self.config.canonical_lang), contents[0]
        )
        translations: list[ScrapedTranslation] = []
        seen = {canonical.lang}
        for content in contents:
            if content.lang in seen:
                continue
            seen.add(content.lang)
            translations.append(ScrapedTranslation(
                lang=content.lang,
                title=content.title.strip(),
                description=content.description,
                source_url=source_url,
            ))
        return canonical, translations

    @staticmethod
    def _external_id(shortcode: str, index: int, stored: int) -> str:
        """`ig-{shortcode}`, qualified by the event's index in the *stored*
        extraction when the post announced several events. The stored order is
        frozen at parse time; the post-gate order is not (a date passing
        shifts it), so indexing off the gated list would rename events and
        duplicate them on upsert."""
        return f"ig-{shortcode}" if stored <= 1 else f"ig-{shortcode}-{index}"
