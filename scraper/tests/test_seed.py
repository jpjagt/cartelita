from cartelera.seed import seed
from cartelera.models import Category, Venue, List, ListVenue


def test_seed_is_idempotent(session):
    seed(session)
    seed(session)  # second run must not duplicate
    assert session.query(Category).count() == 4
    assert session.query(Venue).filter_by(slug="jamboree").count() == 1
    assert session.query(List).filter_by(slug="jazz").count() == 1
    assert session.query(ListVenue).count() == 1


def test_jamboree_is_jazz(session):
    seed(session)
    v = session.query(Venue).filter_by(slug="jamboree").one()
    assert [c.slug for c in v.categories] == ["jazz"]
