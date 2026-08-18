import pytest
from cartelera.seed import seed, CATEGORIES, CITIES
from cartelera.scrapers import load_all
from cartelera.models import Category, City, Venue, List, ListVenue


def _registered_venues():
    """All venue definitions across all registered sources."""
    return [v for _s, source in load_all().values() for v in source.venues]


def test_seed_is_idempotent(session):
    seed(session)
    seed(session)
    assert session.query(Category).count() == len(CATEGORIES)


def test_seed_creates_all_cities(session):
    seed(session)
    for slug, name in CITIES:
        city = session.query(City).filter_by(slug=slug).one()
        assert city.name == name


def test_all_registered_venues_seeded(session):
    seed(session)
    for defn in _registered_venues():
        assert session.query(Venue).filter_by(slug=defn.slug).count() == 1, \
            f"missing venue: {defn.slug}"


def test_each_category_list_created_once_per_city(session):
    seed(session)
    # Lists are created lazily from venue memberships, per city; a (city, slug)
    # pair must never be duplicated.
    for lst in session.query(List).all():
        assert session.query(List).filter_by(slug=lst.slug, city_id=lst.city_id).count() == 1


def test_lists_are_scoped_to_the_venue_city(session):
    seed(session)
    for defn in _registered_venues():
        venue = session.query(Venue).filter_by(slug=defn.slug).one()
        for mem in defn.list_memberships:
            lst = (session.query(List)
                   .filter_by(slug=mem.list_slug, city_id=venue.city_id).one())
            assert lst.city_id == venue.city_id


def test_multi_category_venues_have_whitelisted_memberships(session):
    seed(session)
    for defn in _registered_venues():
        if len(defn.list_memberships) <= 1:
            continue
        venue = session.query(Venue).filter_by(slug=defn.slug).one()
        for mem in defn.list_memberships:
            if mem.whitelist_category_slug is None:
                continue
            lst = session.query(List).filter_by(slug=mem.list_slug, city_id=venue.city_id).one()
            cat = session.query(Category).filter_by(slug=mem.whitelist_category_slug).one()
            lv = session.query(ListVenue).filter_by(list_id=lst.id, venue_id=venue.id).one()
            assert lv.whitelist_category_id == cat.id, (
                f"{defn.slug}: expected whitelist={mem.whitelist_category_slug} on {mem.list_slug} list"
            )


def test_single_membership_venues_have_null_whitelist(session):
    seed(session)
    for defn in _registered_venues():
        if len(defn.list_memberships) != 1 or defn.list_memberships[0].whitelist_category_slug is not None:
            continue
        venue = session.query(Venue).filter_by(slug=defn.slug).one()
        mem_def = defn.list_memberships[0]
        lst = session.query(List).filter_by(slug=mem_def.list_slug, city_id=venue.city_id).one()
        lv = session.query(ListVenue).filter_by(list_id=lst.id, venue_id=venue.id).one()
        assert lv.whitelist_category_id is None, f"{defn.slug}: expected null whitelist"


def test_no_duplicate_memberships(session):
    seed(session)
    seed(session)
    total = session.query(ListVenue).count()
    expected = sum(len(defn.list_memberships) for defn in _registered_venues())
    assert total == expected, f"ListVenue count {total} != expected {expected}"


def test_seed_rejects_unknown_city(session, monkeypatch):
    from cartelera.scrapers import REGISTRY
    from cartelera.types import SourceDefinition, VenueDefinition

    load_all()
    bad = SourceDefinition(
        slug="bad-city-venue", name="Bad",
        venues=[VenueDefinition(slug="bad-city-venue", name="Bad", city_slug="atlantis")])

    class _Noop:
        def scrape(self):
            return []

    monkeypatch.setitem(REGISTRY, "bad-city-venue", (_Noop(), bad))
    with pytest.raises(ValueError, match="unknown city slug 'atlantis'"):
        seed(session)
