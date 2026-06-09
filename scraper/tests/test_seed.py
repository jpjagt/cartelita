from cartelera.seed import seed, CATEGORIES
from cartelera.scrapers import load_all
from cartelera.models import Category, Venue, List, ListVenue


def test_seed_is_idempotent(session):
    seed(session)
    seed(session)
    assert session.query(Category).count() == len(CATEGORIES)


def test_all_registered_venues_seeded(session):
    seed(session)
    registry = load_all()
    for slug in registry:
        assert session.query(Venue).filter_by(slug=slug).count() == 1, f"missing venue: {slug}"


def test_each_category_list_created_once(session):
    seed(session)
    for slug, _ in CATEGORIES:
        assert session.query(List).filter_by(slug=slug).count() == 1


def test_multi_category_venues_have_whitelisted_memberships(session):
    seed(session)
    registry = load_all()
    for slug, (scraper, defn) in registry.items():
        if len(defn.list_memberships) <= 1:
            continue
        venue = session.query(Venue).filter_by(slug=slug).one()
        for mem in defn.list_memberships:
            if mem.whitelist_category_slug is None:
                continue
            lst = session.query(List).filter_by(slug=mem.list_slug).one()
            cat = session.query(Category).filter_by(slug=mem.whitelist_category_slug).one()
            lv = session.query(ListVenue).filter_by(list_id=lst.id, venue_id=venue.id).one()
            assert lv.whitelist_category_id == cat.id, (
                f"{slug}: expected whitelist={mem.whitelist_category_slug} on {mem.list_slug} list"
            )


def test_single_membership_venues_have_null_whitelist(session):
    seed(session)
    registry = load_all()
    for slug, (scraper, defn) in registry.items():
        if len(defn.list_memberships) != 1 or defn.list_memberships[0].whitelist_category_slug is not None:
            continue
        venue = session.query(Venue).filter_by(slug=slug).one()
        mem_def = defn.list_memberships[0]
        lst = session.query(List).filter_by(slug=mem_def.list_slug).one()
        lv = session.query(ListVenue).filter_by(list_id=lst.id, venue_id=venue.id).one()
        assert lv.whitelist_category_id is None, f"{slug}: expected null whitelist"


def test_no_duplicate_memberships(session):
    seed(session)
    seed(session)
    total = session.query(ListVenue).count()
    # Recount from definitions
    registry = load_all()
    expected = sum(len(defn.list_memberships) for _, defn in registry.values())
    assert total == expected, f"ListVenue count {total} != expected {expected}"
