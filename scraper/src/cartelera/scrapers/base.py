from __future__ import annotations
from typing import Protocol
from cartelera.types import ScrapedEvent


class Scraper(Protocol):
    """Uniform per-venue scraper interface.

    `venue_slug` ties the scraper to a seeded venue row.
    `scrape()` returns fully-categorized ScrapedEvents, or raises on failure.
    """
    venue_slug: str

    def scrape(self) -> list[ScrapedEvent]:
        ...
