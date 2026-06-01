from cartelera.scrapers.base import Scraper

# Populated as scrapers are added. Maps venue_slug -> Scraper instance.
REGISTRY: dict[str, Scraper] = {}


def register(scraper: Scraper) -> None:
    REGISTRY[scraper.venue_slug] = scraper
