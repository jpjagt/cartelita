import importlib
import pkgutil

from cartelera.scrapers.base import Scraper
from cartelera.types import VenueDefinition

# Maps venue_slug -> (Scraper instance, VenueDefinition).
REGISTRY: dict[str, tuple[Scraper, VenueDefinition]] = {}

# Modules in this package that are not venue scrapers and should not be imported
# for registration.
_NON_SCRAPER_MODULES = {"base", "price"}


def register(scraper: Scraper, venue: VenueDefinition) -> None:
    REGISTRY[scraper.venue_slug] = (scraper, venue)


def load_all() -> dict[str, tuple[Scraper, VenueDefinition]]:
    """Import every scraper module so each runs its register(...) call.

    Discovers modules automatically, so adding a new scraper file needs no
    edits here or in seed.py.
    """
    for module in pkgutil.iter_modules(__path__):
        if module.name.startswith("_") or module.name in _NON_SCRAPER_MODULES:
            continue
        importlib.import_module(f"{__name__}.{module.name}")
    return REGISTRY
