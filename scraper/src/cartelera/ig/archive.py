from __future__ import annotations
import datetime as dt
from sqlalchemy import select
from sqlalchemy.orm import Session
from cartelera.models import IgPost, IgPostImage, IgSession
from cartelera.ig.types import CapturedPost

_SESSION_ROW_ID = 1


def upsert_posts(session: Session, source_slug: str, posts: list[CapturedPost]) -> int:
    """Insert posts (and their images) whose shortcode is new.

    A captured post is immutable history: existing rows are never modified,
    even if the caption/images passed in differ. Runs in the caller's
    transaction; caller commits/rolls back. Returns the number of newly
    inserted posts."""
    if not posts:
        return 0
    shortcodes = [p.shortcode for p in posts]
    existing = set(session.scalars(
        select(IgPost.shortcode).where(IgPost.shortcode.in_(shortcodes))
    ).all())
    inserted = 0
    for p in posts:
        if p.shortcode in existing:
            continue
        row = IgPost(
            shortcode=p.shortcode,
            source_slug=source_slug,
            handle=p.handle,
            caption=p.caption,
            posted_at=p.posted_at,
        )
        row.images = [
            IgPostImage(idx=idx, url=img.url, content_type=img.content_type, data=img.data)
            for idx, img in enumerate(p.images)
        ]
        session.add(row)
        existing.add(p.shortcode)  # guard against duplicate shortcodes within the same batch
        inserted += 1
    session.flush()
    return inserted


def archived_shortcodes(session: Session, handle: str) -> set[str]:
    return set(session.scalars(
        select(IgPost.shortcode).where(IgPost.handle == handle)
    ).all())


def posts_missing_extraction(session: Session, source_slug: str) -> list[IgPost]:
    """Rows with extraction IS NULL, oldest posted_at first."""
    return list(session.scalars(
        select(IgPost)
        .where(IgPost.source_slug == source_slug, IgPost.extraction.is_(None))
        .order_by(IgPost.posted_at.asc())
    ).all())


def extracted_posts(session: Session, source_slug: str) -> list[IgPost]:
    """Rows with extraction IS NOT NULL, oldest posted_at first."""
    return list(session.scalars(
        select(IgPost)
        .where(IgPost.source_slug == source_slug, IgPost.extraction.is_not(None))
        .order_by(IgPost.posted_at.asc())
    ).all())


def save_extraction(
    session: Session, shortcode: str, extraction: dict, model_id: str, prompt_version: int
) -> None:
    """Set the four extraction columns (extracted_at = now).

    Raises ValueError if the row already has an extraction (single-parse
    invariant) or the shortcode is unknown."""
    row = session.get(IgPost, shortcode)
    if row is None:
        raise ValueError(f"unknown ig_post shortcode {shortcode!r}")
    if row.extraction is not None:
        raise ValueError(
            f"ig_post {shortcode!r} already has an extraction; a post is parsed "
            "at most once in production (prompt_version is provenance, not a cache key)"
        )
    row.extraction = extraction
    row.model_id = model_id
    row.prompt_version = prompt_version
    row.extracted_at = dt.datetime.now(dt.timezone.utc)
    session.flush()


def get_session_state(session: Session) -> dict | None:
    row = session.get(IgSession, _SESSION_ROW_ID)
    return row.storage_state if row else None


def set_session_state(session: Session, state: dict) -> None:
    """Upsert the single-row ig_session storage_state."""
    row = session.get(IgSession, _SESSION_ROW_ID)
    if row is None:
        session.add(IgSession(id=_SESSION_ROW_ID, storage_state=state))
    else:
        row.storage_state = state
        row.updated_at = dt.datetime.now(dt.timezone.utc)
    session.flush()
