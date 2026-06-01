import datetime as dt
from cartelera.types import ScrapedEvent, ScrapedTranslation, ScrapeResult


def test_scraped_event_minimal_required_fields():
    ev = ScrapedEvent(
        title="X", start_date=dt.date(2026, 6, 1),
        source_url="https://x/", category_slugs=["jazz"],
    )
    assert ev.price is None
    assert ev.category_slugs == ["jazz"]
    assert ev.translations == []


def test_scraped_event_carries_translations():
    ev = ScrapedEvent(
        title="X", start_date=dt.date(2026, 6, 1), source_url="https://x/",
        category_slugs=["film"],
        translations=[ScrapedTranslation(lang="en", title="EN")],
    )
    assert ev.translations[0].lang == "en"
    assert ev.translations[0].description is None


def test_scrape_result_defaults():
    r = ScrapeResult(venue_slug="jamboree", ok=True)
    assert r.events == [] and r.error is None
