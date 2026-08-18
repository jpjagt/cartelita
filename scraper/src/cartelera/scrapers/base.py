from __future__ import annotations
from typing import Protocol
from cartelera.types import ScrapedEvent


class Scraper(Protocol):
    """Uniform per-source scraper interface.

    A scraper's identity comes from its registration (see scrapers/__init__.py):
    single-venue scrapers register via register(scraper, venue) and by
    convention also carry a `venue_slug` attribute; multi-venue sources
    register via register_source(scraper, source) and set `venue_slug` on each
    ScrapedEvent instead.

    `scrape()` returns fully-categorized ScrapedEvents, or raises on failure.
    """

    def scrape(self) -> list[ScrapedEvent]:
        ...
