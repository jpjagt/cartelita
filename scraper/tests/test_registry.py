from cartelera.scrapers import REGISTRY, register
from cartelera.types import VenueDefinition


def test_register_adds_scraper_by_venue_slug():
    class Fake:
        venue_slug = "test-venue"
        def scrape(self):
            return []
    fake = Fake()
    venue = VenueDefinition(slug="test-venue", name="Test Venue", city_slug="barcelona")
    register(scraper=fake, venue=venue)
    scraper, venue_def = REGISTRY["test-venue"]
    assert scraper is fake
    assert venue_def.slug == "test-venue"
    # cleanup so we don't pollute other tests
    del REGISTRY["test-venue"]
