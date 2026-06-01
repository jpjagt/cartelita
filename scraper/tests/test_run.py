import datetime as dt
from cartelera.seed import seed
from cartelera.models import Event
from cartelera.types import ScrapedEvent
from cartelera.scrapers import REGISTRY
from cartelera.run import run_one, run_all


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
    monkeypatch.setitem(REGISTRY, "jamboree", (_FakeScraper(events=[ev]), REGISTRY["jamboree"][1]))
    result = run_one(session, "jamboree")
    assert result.ok and len(result.events) == 1
    assert session.query(Event).count() == 1


def test_failing_scraper_is_isolated_and_keeps_existing_data(session, monkeypatch):
    seed(session)
    good = ScrapedEvent(title="Old", start_date=dt.date(2026, 6, 2),
                        source_url="https://x/", category_slugs=["jazz"], external_id="1")
    jamboree_venue = REGISTRY["jamboree"][1]
    monkeypatch.setitem(REGISTRY, "jamboree", (_FakeScraper(events=[good]), jamboree_venue))
    run_one(session, "jamboree")
    # now the venue's scraper breaks
    monkeypatch.setitem(REGISTRY, "jamboree", (_FakeScraper(boom=True), jamboree_venue))
    result = run_one(session, "jamboree")
    assert not result.ok
    assert "site changed" in result.error
    # existing data untouched
    assert session.query(Event).count() == 1


def test_run_all_isolates_failures_across_venues(session, monkeypatch):
    seed(session)

    class _Fake:
        def __init__(self, slug, events=None, boom=False):
            self.venue_slug = slug
            self._events = events or []
            self._boom = boom
        def scrape(self):
            if self._boom:
                raise RuntimeError("boom")
            return self._events

    from cartelera.types import VenueDefinition

    good_ev = ScrapedEvent(title="Good", start_date=dt.date(2026, 6, 2),
                           source_url="https://x/", category_slugs=["jazz"], external_id="1")
    # Replace REGISTRY with two venues: jamboree (good) + a broken one.
    # Both must reference seeded venues; seed only creates 'jamboree', so the
    # broken scraper also targets 'jamboree' is not possible (same slug). Instead,
    # register the good scraper under 'jamboree' and a broken one under a slug
    # whose venue we add here.
    from cartelera.models import Venue, City
    bcn = session.query(City).filter_by(slug="barcelona").one()
    session.add(Venue(slug="broken-venue", name="Broken", city_id=bcn.id))
    session.commit()

    jamboree_venue = REGISTRY["jamboree"][1]
    broken_venue = VenueDefinition(slug="broken-venue", name="Broken", city_slug="barcelona")
    monkeypatch.setattr("cartelera.run.REGISTRY", {
        "jamboree": (_Fake("jamboree", events=[good_ev]), jamboree_venue),
        "broken-venue": (_Fake("broken-venue", boom=True), broken_venue),
    })
    results = run_all(session)
    by_slug = {r.venue_slug: r for r in results}
    assert by_slug["jamboree"].ok is True
    assert by_slug["broken-venue"].ok is False
    # the good venue's event is committed despite the other failing
    assert session.query(Event).count() == 1
