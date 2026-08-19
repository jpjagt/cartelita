from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field


@dataclass
class RawImage:
    """One downloaded image of a captured post."""
    url: str  # source CDN URL
    content_type: str
    data: bytes


@dataclass
class RosterVenue:
    """One venue an IG source may emit events for, as the LLM is told about it.

    The roster is a source's editorial whitelist (AGENTS.md: a source is the
    unit of scraping, a venue the unit of curation) rendered for the prompt:
    the model must pick `venue_slug` from these slugs and `category` from that
    venue's `category_slugs`."""
    slug: str
    name: str
    category_slugs: list[str]
    hints: str | None = None  # free-text prompt hints about this venue's posting style


@dataclass
class CapturedPost:
    """One Instagram post as captured from the timeline XHR, before download."""
    shortcode: str
    handle: str
    caption: str | None
    posted_at: dt.datetime | None  # tz-aware when present
    image_urls: list[str]  # ordered as posted
    # Filled once each image is downloaded; each image's url matches an entry
    # of image_urls. Empty until download runs.
    images: list[RawImage] = field(default_factory=list)


@dataclass
class CaptureResult:
    """What one `capture_new_posts` call produced.

    `storage_state` is the session as it stood when the browser closed — IG
    rotates session cookies over the course of a run, so the caller should
    re-persist it after a successful capture rather than let the stored
    session drift out of sync with what was actually used."""
    posts: dict[str, list[CapturedPost]]
    storage_state: dict
