import importlib
import pkgutil

from cartelera.scrapers.base import Scraper
from cartelera.types import SourceDefinition, VenueDefinition

# Maps source_slug -> (Scraper instance, SourceDefinition). A source is the
# unit of scraping; most are 1:1 with a venue (see register()), but an
# aggregator or social-media source can feed several venues.
REGISTRY: dict[str, tuple[Scraper, SourceDefinition]] = {}

# Modules in this package that are not venue scrapers and should not be imported
# for registration.
_NON_SCRAPER_MODULES = {"base", "price", "esora"}


def register(scraper: Scraper, venue: VenueDefinition) -> None:
    """Single-venue sugar: wraps the venue in a SourceDefinition whose slug is
    the venue's slug. The common case — a scraper for one venue's own site."""
    register_source(
        scraper, SourceDefinition(slug=venue.slug, name=venue.name, venues=[venue])
    )


def register_source(scraper: Scraper, source: SourceDefinition) -> None:
    REGISTRY[source.slug] = (scraper, source)


def load_all() -> dict[str, tuple[Scraper, SourceDefinition]]:
    """Import every scraper module so each runs its register(...) call.

    Discovers modules automatically, so adding a new scraper file needs no
    edits here or in seed.py.
    """
    for module in pkgutil.iter_modules(__path__):
        if module.name.startswith("_") or module.name in _NON_SCRAPER_MODULES:
            continue
        importlib.import_module(f"{__name__}.{module.name}")
    return REGISTRY
