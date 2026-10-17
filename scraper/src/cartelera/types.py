from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, model_validator


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
    """Outcome of running one source's scraper. `ok` is False when the run's
    data was not written (verdict broken / site_down); see cartelera.health."""
    source_slug: str
    ok: bool
    events: list[ScrapedEvent] = field(default_factory=list)
    error: str | None = None
    verdict: str | None = None           # healthy | degraded | broken | site_down
    fired: list[str] = field(default_factory=list)   # degraded rules, human-readable
    hidden: int = 0                      # events newly hidden by this run
    # Venues this run created (a venue-discovering source), as recorded in
    # scrape_run.metrics["new_venues"]: {slug, name, address, categories, events}.
    new_venues: list[dict] = field(default_factory=list)
    # Venues of a multi-venue source degraded on their own this run (the
    # source verdict stays healthy; their events are not missed/hidden).
    degraded_venues: list[str] = field(default_factory=list)
    # Categories this run added to code-defined venues of a source with
    # `extends_venue_categories`, as recorded in
    # scrape_run.metrics["new_categories"]: {slug, name, category, events}.
    new_categories: list[dict] = field(default_factory=list)


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
    # Explicit map coordinates (WGS84). When set, seed writes them and
    # geocoding never touches the venue — use this to fix a venue the
    # geocoder misses or places wrong (see cartelera.geocode).
    lat: float | None = None
    lng: float | None = None

    @model_validator(mode="after")
    def _coords_together(self) -> "VenueDefinition":
        if (self.lat is None) != (self.lng is None):
            raise ValueError(f"venue {self.slug!r}: set both lat and lng, or neither")
        return self


class SourceDefinition(BaseModel):
    """A source is the unit of SCRAPING; a venue the unit of CURATION.

    Most sources are a venue's own site (1:1 — see the register() sugar, which
    wraps a bare VenueDefinition). Aggregators (e.g. a ticketing site covering
    a whole city) and social-media profiles are sources too; their `venues`
    list doubles as the editorial whitelist: the runner rejects events for any
    venue not listed here — unless the scraper also discovers venues at run
    time (an opt-out source, see scrapers.base.DiscoversVenues and
    cartelera.discovery), in which case `venues` holds only the overrides.

    `extends_venue_categories` (opt-in; today only jazzin.amsterdam): when an
    event at one of `venues` carries a category the venue doesn't have yet,
    the run adds that category to the venue, plus a list membership
    whitelisted to it (list slug = category slug), before writing the events —
    the source's own categorization decides where its venues are listed. The
    code-defined categories are the seeded minimum; the DB only ever gains
    categories (never loses them, also not on re-seed). For every other source
    a venue's categories are strictly code-defined."""
    slug: str
    name: str
    venues: list[VenueDefinition] = Field(min_length=1)
    extends_venue_categories: bool = False
