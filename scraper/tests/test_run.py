import datetime as dt
from cartelera.seed import seed
from cartelera.models import Event
from cartelera.types import ScrapedEvent
from cartelera.scrapers import REGISTRY
from cartelera.run import run_one, run_all, _resolve_run_targets


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

    from cartelera.types import SourceDefinition, VenueDefinition

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

    jamboree_source = REGISTRY["jamboree"][1]
    broken_source = SourceDefinition(
        slug="broken-venue", name="Broken",
        venues=[VenueDefinition(slug="broken-venue", name="Broken", city_slug="barcelona")])
    monkeypatch.setattr("cartelera.run.REGISTRY", {
        "jamboree": (_Fake("jamboree", events=[good_ev]), jamboree_source),
        "broken-venue": (_Fake("broken-venue", boom=True), broken_source),
    })
    results = run_all(session)
    by_slug = {r.source_slug: r for r in results}
    assert by_slug["jamboree"].ok is True
    assert by_slug["broken-venue"].ok is False
    # the good venue's event is committed despite the other failing
    assert session.query(Event).count() == 1


# --- run target resolution (pure: uses the real populated REGISTRY) ---


def test_resolve_targets_defaults_to_all():
    assert _resolve_run_targets([]) == list(REGISTRY)
    assert _resolve_run_targets(["all"]) == list(REGISTRY)


def test_resolve_targets_by_category():
    film = _resolve_run_targets(["-c", "film"])
    assert "filmoteca" in film and "cines-verdi" in film
    # category-filtered sources all actually have a venue carrying that category
    assert all(
        any("film" in v.category_slugs for v in REGISTRY[s][1].venues) for s in film
    )
    # jazz venues are disjoint from the film set
    assert "jamboree" not in film
    assert _resolve_run_targets(["--category", "jazz"]) == _resolve_run_targets(["-c", "jazz"])


def test_resolve_targets_by_city():
    yerevan = _resolve_run_targets([":yerevan"])
    assert yerevan
    # city-filtered sources all actually have a venue in that city
    assert all(
        any(v.city_slug == "yerevan" for v in REGISTRY[s][1].venues) for s in yerevan
    )
    # barcelona venues are disjoint from the yerevan set
    assert "jamboree" not in yerevan
    barcelona = _resolve_run_targets([":barcelona"])
    assert "jamboree" in barcelona


def test_resolve_targets_rejects_unknown_city():
    assert _resolve_run_targets([":bogus"]) is None
    assert _resolve_run_targets([":"]) is None


def test_resolve_targets_comma_and_space_separated():
    assert _resolve_run_targets(["cines-verdi,phenomena"]) == ["cines-verdi", "phenomena"]
    assert _resolve_run_targets(["cines-verdi", "phenomena"]) == ["cines-verdi", "phenomena"]


def test_resolve_targets_rejects_unknown_slug_and_category():
    assert _resolve_run_targets(["cines-verdi,nope"]) is None
    assert _resolve_run_targets(["-c", "bogus"]) is None
    assert _resolve_run_targets(["-c"]) is None


# --- multi-venue sources (aggregators, social-media profiles) ---


def _multi_source(session):
    """Register (in the DB + a REGISTRY entry shape) a 2-venue source."""
    from cartelera.models import Venue, City
    from cartelera.types import SourceDefinition, VenueDefinition

    bcn = session.query(City).filter_by(slug="barcelona").one()
    for slug in ("agg-venue-a", "agg-venue-b"):
        if not session.query(Venue).filter_by(slug=slug).one_or_none():
            session.add(Venue(slug=slug, name=slug, city_id=bcn.id))
    session.commit()
    return SourceDefinition(
        slug="agg", name="Aggregator",
        venues=[
            VenueDefinition(slug="agg-venue-a", name="A", city_slug="barcelona"),
            VenueDefinition(slug="agg-venue-b", name="B", city_slug="barcelona"),
        ])


def test_multi_venue_source_groups_events_per_venue(session, monkeypatch):
    seed(session)
    source = _multi_source(session)
    evs = [
        ScrapedEvent(title="A1", start_date=dt.date(2026, 6, 2), source_url="https://a/1",
                     category_slugs=["jazz"], external_id="a1", venue_slug="agg-venue-a"),
        ScrapedEvent(title="B1", start_date=dt.date(2026, 6, 3), source_url="https://b/1",
                     category_slugs=["jazz"], external_id="b1", venue_slug="agg-venue-b"),
    ]
    monkeypatch.setitem(REGISTRY, "agg", (_FakeScraper(events=evs), source))
    result = run_one(session, "agg")
    assert result.ok, result.error
    from cartelera.models import Venue
    a = session.query(Venue).filter_by(slug="agg-venue-a").one()
    b = session.query(Venue).filter_by(slug="agg-venue-b").one()
    assert {e.title for e in a.events} == {"A1"}
    assert {e.title for e in b.events} == {"B1"}


def test_multi_venue_source_fails_fast_on_missing_venue_slug(session, monkeypatch):
    seed(session)
    source = _multi_source(session)
    evs = [ScrapedEvent(title="X", start_date=dt.date(2026, 6, 2), source_url="https://x/",
                        category_slugs=["jazz"], external_id="x1")]  # no venue_slug
    monkeypatch.setitem(REGISTRY, "agg", (_FakeScraper(events=evs), source))
    result = run_one(session, "agg")
    assert not result.ok
    assert "must set venue_slug" in result.error


def test_multi_venue_source_rejects_unwhitelisted_venue(session, monkeypatch):
    seed(session)
    source = _multi_source(session)
    evs = [ScrapedEvent(title="X", start_date=dt.date(2026, 6, 2), source_url="https://x/",
                        category_slugs=["jazz"], external_id="x1", venue_slug="jamboree")]
    monkeypatch.setitem(REGISTRY, "agg", (_FakeScraper(events=evs), source))
    result = run_one(session, "agg")
    assert not result.ok
    assert "not among source" in result.error


def test_single_venue_source_fills_in_venue_slug(session, monkeypatch):
    seed(session)
    # venue_slug left unset on the event: resolves to the source's sole venue.
    ev = ScrapedEvent(title="X", start_date=dt.date(2026, 6, 2), source_url="https://x/",
                      category_slugs=["jazz"], external_id="1")
    monkeypatch.setitem(REGISTRY, "jamboree", (_FakeScraper(events=[ev]), REGISTRY["jamboree"][1]))
    result = run_one(session, "jamboree")
    assert result.ok
    assert session.query(Event).one().venue.slug == "jamboree"
