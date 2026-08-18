from cartelera.scrapers import REGISTRY, register, register_source
from cartelera.types import SourceDefinition, VenueDefinition


class _Fake:
    def scrape(self):
        return []


def test_register_wraps_venue_in_single_venue_source():
    fake = _Fake()
    venue = VenueDefinition(slug="test-venue", name="Test Venue", city_slug="barcelona")
    register(scraper=fake, venue=venue)
    scraper, source = REGISTRY["test-venue"]
    assert scraper is fake
    assert isinstance(source, SourceDefinition)
    assert source.slug == "test-venue"
    assert [v.slug for v in source.venues] == ["test-venue"]
    # cleanup so we don't pollute other tests
    del REGISTRY["test-venue"]


def test_register_source_keys_by_source_slug():
    fake = _Fake()
    source = SourceDefinition(
        slug="test-aggregator",
        name="Test Aggregator",
        venues=[
            VenueDefinition(slug="venue-a", name="A", city_slug="yerevan"),
            VenueDefinition(slug="venue-b", name="B", city_slug="yerevan"),
        ],
    )
    register_source(scraper=fake, source=source)
    scraper, stored = REGISTRY["test-aggregator"]
    assert scraper is fake
    assert [v.slug for v in stored.venues] == ["venue-a", "venue-b"]
    del REGISTRY["test-aggregator"]


def test_source_requires_at_least_one_venue():
    import pytest
    with pytest.raises(Exception):
        SourceDefinition(slug="empty", name="Empty", venues=[])
