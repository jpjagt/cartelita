from cartelera.seed import seed
from cartelera.models import Category, Venue, List, ListVenue


def test_seed_is_idempotent(session):
    seed(session)
    seed(session)  # second run must not duplicate
    assert session.query(Category).count() == 5
    for slug in ("jamboree", "harlem-jazz-club", "robadors", "casa-figari", "sala-beckett", "big-bang-bar", "filmoteca"):
        assert session.query(Venue).filter_by(slug=slug).count() == 1
    for slug in ("jazz", "club", "theater", "film"):
        assert session.query(List).filter_by(slug=slug).count() == 1
    # Memberships: jazz list = jamboree+harlem+robadors+casa_figari+big_bang (5);
    # club list = jamboree+casa_figari+big_bang (3); theater list = beckett (1);
    # film list = filmoteca (1).
    assert session.query(ListVenue).count() == 10


def test_jamboree_is_jazz_and_club(session):
    seed(session)
    v = session.query(Venue).filter_by(slug="jamboree").one()
    assert sorted(c.slug for c in v.categories) == ["club", "jazz"]


def test_casa_figari_is_jazz_and_club(session):
    seed(session)
    v = session.query(Venue).filter_by(slug="casa-figari").one()
    assert sorted(c.slug for c in v.categories) == ["club", "jazz"]


def test_single_category_venues(session):
    seed(session)
    harlem = session.query(Venue).filter_by(slug="harlem-jazz-club").one()
    robadors = session.query(Venue).filter_by(slug="robadors").one()
    beckett = session.query(Venue).filter_by(slug="sala-beckett").one()
    filmoteca = session.query(Venue).filter_by(slug="filmoteca").one()
    assert [c.slug for c in harlem.categories] == ["jazz"]
    assert [c.slug for c in robadors.categories] == ["jazz"]
    assert [c.slug for c in beckett.categories] == ["theater"]
    assert [c.slug for c in filmoteca.categories] == ["film"]


def test_multi_category_venues_whitelist_their_category(session):
    seed(session)
    jazz_list = session.query(List).filter_by(slug="jazz").one()
    club_list = session.query(List).filter_by(slug="club").one()
    jazz_cat = session.query(Category).filter_by(slug="jazz").one()
    club_cat = session.query(Category).filter_by(slug="club").one()
    # Multi-category venues (jamboree, casa-figari, big-bang-bar) appear in each list
    # whitelisted to that list's category.
    for venue_slug in ("jamboree", "casa-figari", "big-bang-bar"):
        v = session.query(Venue).filter_by(slug=venue_slug).one()
        jazz_mem = session.query(ListVenue).filter_by(list_id=jazz_list.id, venue_id=v.id).one()
        club_mem = session.query(ListVenue).filter_by(list_id=club_list.id, venue_id=v.id).one()
        assert jazz_mem.whitelist_category_id == jazz_cat.id
        assert club_mem.whitelist_category_id == club_cat.id


def test_single_category_venues_have_null_whitelist(session):
    seed(session)
    jazz_list = session.query(List).filter_by(slug="jazz").one()
    theater_list = session.query(List).filter_by(slug="theater").one()
    film_list = session.query(List).filter_by(slug="film").one()
    for venue_slug, lst in (("harlem-jazz-club", jazz_list),
                            ("robadors", jazz_list),
                            ("sala-beckett", theater_list),
                            ("filmoteca", film_list)):
        v = session.query(Venue).filter_by(slug=venue_slug).one()
        mem = session.query(ListVenue).filter_by(list_id=lst.id, venue_id=v.id).one()
        assert mem.whitelist_category_id is None
