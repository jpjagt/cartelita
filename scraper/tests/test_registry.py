from cartelera.scrapers import REGISTRY, register


def test_register_adds_scraper_by_venue_slug():
    class Fake:
        venue_slug = "test-venue"
        def scrape(self):
            return []
    fake = Fake()
    register(fake)
    assert REGISTRY["test-venue"] is fake
    # cleanup so we don't pollute other tests
    del REGISTRY["test-venue"]
