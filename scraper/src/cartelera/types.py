from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


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
    # Stable, per-OCCURRENCE dedup key within a venue: the upsert dedups on
    # (venue, external_id) and one Event row is one occurrence. If the venue's
    # natural id is coarser than an occurrence (e.g. a film slug that screens on
    # many dates), qualify it with date+time — a bare coarser id silently collapses
    # occurrences (upsert raises if two events in one batch share one).
    external_id: str | None = None
    recurrence_hint: str | None = None
    # Performance/source language as a concise display string, on the price
    # convention: None = unknown, otherwise exactly what the source states
    # ("VOSE", "hy", "ru", "non-verbal"). Never parsed or inferred.
    language: str | None = None
    annotations: list[str] = field(default_factory=list)  # free-form tags/labels
    # Which of the source's venues this event belongs to. None is allowed only
    # for single-venue sources (the runner fills it in); a multi-venue source
    # must set it on every event, and the runner fails fast otherwise.
    venue_slug: str | None = None
    translations: list[ScrapedTranslation] = field(default_factory=list)


@dataclass
class ScrapeResult:
    """Outcome of running one source's scraper."""
    source_slug: str
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
    instagram_url: str | None = None
    category_slugs: list[str] = []
    list_memberships: list[ListMembership] = []


class SourceDefinition(BaseModel):
    """A source is the unit of SCRAPING; a venue the unit of CURATION.

    Most sources are a venue's own site (1:1 — see the register() sugar, which
    wraps a bare VenueDefinition). Aggregators (e.g. a ticketing site covering
    a whole city) and social-media profiles are sources too; their `venues`
    list doubles as the editorial whitelist: the runner rejects events for any
    venue not listed here."""
    slug: str
    name: str
    venues: list[VenueDefinition] = Field(min_length=1)
