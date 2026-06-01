import datetime as dt
from cartelera.seed import seed
from cartelera.models import Event
from cartelera.types import ScrapedEvent
from cartelera.scrapers import REGISTRY
from cartelera.run import run_one


class _FakeScraper:
    venue_slug = "jamboree"

    def __init__(self, events=None, boom=False):
        self._events = events or []
        self._boom = boom

    def scrape(self):
        if self._boom:
            raise RuntimeError("site changed")
        return self._events


def test_successful_run_writes_events(session, monkeypatch):
    seed(session)
    ev = ScrapedEvent(title="X", start_date=dt.date(2026, 6, 2),
                      source_url="https://x/", category_slugs=["jazz"], external_id="1")
    monkeypatch.setitem(REGISTRY, "jamboree", _FakeScraper(events=[ev]))
    result = run_one(session, "jamboree")
    assert result.ok and len(result.events) == 1
    assert session.query(Event).count() == 1


def test_failing_scraper_is_isolated_and_keeps_existing_data(session, monkeypatch):
    seed(session)
    good = ScrapedEvent(title="Old", start_date=dt.date(2026, 6, 2),
                        source_url="https://x/", category_slugs=["jazz"], external_id="1")
    monkeypatch.setitem(REGISTRY, "jamboree", _FakeScraper(events=[good]))
    run_one(session, "jamboree")
    # now the venue's scraper breaks
    monkeypatch.setitem(REGISTRY, "jamboree", _FakeScraper(boom=True))
    result = run_one(session, "jamboree")
    assert not result.ok
    assert "site changed" in result.error
    # existing data untouched
    assert session.query(Event).count() == 1
