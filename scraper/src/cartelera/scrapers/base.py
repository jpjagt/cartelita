from __future__ import annotations
from typing import Protocol, runtime_checkable
from cartelera.types import ScrapedEvent, VenueDefinition


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


@runtime_checkable
class DiscoversVenues(Protocol):
    """Optional extra for an OPT-OUT multi-venue source (jazzin.amsterdam):
    besides the venues its SourceDefinition declares (the overrides), it may
    emit events for venues it found in the feed. After `scrape()`, the runner
    calls `discovered_venues()` and creates/updates those venues (and their
    list memberships) in the same transaction as the events — see
    cartelera.discovery. A discovered slug that another source (or a code-
    defined venue) already owns is refused and its events skipped."""

    def discovered_venues(self) -> list[VenueDefinition]:
        """The venues the last scrape() emitted events for that the source's
        SourceDefinition doesn't declare."""
        ...
