from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field
from pydantic import BaseModel


@dataclass
class ScrapedTranslation:
    """Additional-language content for an event, scraped from its own page."""
    lang: str                            # 'ca' / 'es' / 'en'
    title: str
    description: str | None = None
    source_url: str | None = None


@dataclass
class ScrapedEvent:
    """The uniform output of every scraper: one fully-categorized occurrence.
    `title`/`description`/`source_url` are the canonical (default) content;
    `translations` holds any additional-language content (usually empty)."""
    title: str
    start_date: dt.date
    source_url: str
    category_slugs: list[str]            # one or more
    start_time: dt.time | None = None
    start_times: list[dt.time] = field(default_factory=list)  # all sessions; start_time is the earliest
    end_date: dt.date | None = None
    end_time: dt.time | None = None
    # Price convention: None = unknown, "free" = no admission cost,
    # "sold-out" = tickets exhausted, otherwise a concise display string
    # (e.g. "10€", "10–22€"). Skip member/discount tiers; show a range
    # only when tiers differ meaningfully.
    price: str | None = None
    description: str | None = None
    image_url: str | None = None
    external_id: str | None = None
    recurrence_hint: str | None = None
    annotations: list[str] = field(default_factory=list)  # free-form tags/labels
    translations: list[ScrapedTranslation] = field(default_factory=list)


@dataclass
class ScrapeResult:
    """Outcome of running one venue's scraper."""
    venue_slug: str
    ok: bool
    events: list[ScrapedEvent] = field(default_factory=list)
    error: str | None = None


class ListMembership(BaseModel):
    list_slug: str
    whitelist_category_slug: str | None = None


class VenueDefinition(BaseModel):
    slug: str
    name: str
    city_slug: str
    address: str | None = None
    site_url: str | None = None
    category_slugs: list[str] = []
    list_memberships: list[ListMembership] = []
