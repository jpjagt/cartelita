from cartelera.seed import seed
from cartelera.models import Category, Venue, List, ListVenue


def test_seed_is_idempotent(session):
    seed(session)
    seed(session)  # second run must not duplicate
    assert session.query(Category).count() == 5
    assert session.query(Venue).filter_by(slug="jamboree").count() == 1
    assert session.query(List).filter_by(slug="jazz").count() == 1
    assert session.query(List).filter_by(slug="club").count() == 1
    # Jamboree appears once in each of the two lists (jazz + club).
    assert session.query(ListVenue).count() == 2


def test_jamboree_is_jazz_and_club(session):
    seed(session)
    v = session.query(Venue).filter_by(slug="jamboree").one()
    assert sorted(c.slug for c in v.categories) == ["club", "jazz"]


def test_lists_whitelist_their_category(session):
    seed(session)
    jazz_list = session.query(List).filter_by(slug="jazz").one()
    club_list = session.query(List).filter_by(slug="club").one()
    jazz_cat = session.query(Category).filter_by(slug="jazz").one()
    club_cat = session.query(Category).filter_by(slug="club").one()
    jazz_mem = session.query(ListVenue).filter_by(list_id=jazz_list.id).one()
    club_mem = session.query(ListVenue).filter_by(list_id=club_list.id).one()
    assert jazz_mem.whitelist_category_id == jazz_cat.id
    assert club_mem.whitelist_category_id == club_cat.id
