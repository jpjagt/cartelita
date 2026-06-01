from cartelera.scrapers.base import Scraper
from cartelera.types import VenueDefinition

# Maps venue_slug -> (Scraper instance, VenueDefinition).
REGISTRY: dict[str, tuple[Scraper, VenueDefinition]] = {}


def register(scraper: Scraper, venue: VenueDefinition) -> None:
    REGISTRY[scraper.venue_slug] = (scraper, venue)
