from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field


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
    end_date: dt.date | None = None
    end_time: dt.time | None = None
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
