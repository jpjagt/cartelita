from cartelera.seed import seed
from cartelera.models import Category, Venue, List, ListVenue


def test_seed_is_idempotent(session):
    seed(session)
    seed(session)  # second run must not duplicate
    assert session.query(Category).count() == 9
    music_theater_venues = ("jamboree", "harlem-jazz-club", "robadors", "casa-figari", "sala-beckett", "big-bang-bar", "tnc")
    cinema_venues = ("filmoteca", "cines-verdi", "renoir-floridablanca", "phenomena",
                     "zumzeig", "cinema-malda", "sala-montjuic", "cinemes-girona", "espai-texas")
    classical_venues = ("palau-musica", "auditori", "meam", "santa-maria-del-mar",
                        "santa-maria-del-pi", "ateneu-barcelones", "generalitat-carillo", "liceu")
    for slug in music_theater_venues + cinema_venues + classical_venues:
        assert session.query(Venue).filter_by(slug=slug).count() == 1
    for slug in ("jazz", "club", "theater", "film", "classical", "flamenco", "dance", "kids", "pop"):
        assert session.query(List).filter_by(slug=slug).count() == 1
    # Memberships: jazz list = jamboree+harlem+robadors+casa_figari+big_bang + palau+auditori+meam + beckett (9);
    # club list = jamboree+casa_figari+big_bang (3); theater list = beckett+tnc (2);
    # film list = all 9 cinema venues (9);
    # classical list = palau+auditori+meam + mar+pi+ateneu+carillo + liceu (8);
    # flamenco list = palau (1);
    # dance/kids/pop lists = liceu (1 each, 3).
    # Total = 9 + 3 + 2 + 9 + 8 + 1 + 3 = 35.
    assert session.query(ListVenue).count() == 35


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
    assert [c.slug for c in harlem.categories] == ["jazz"]
    assert [c.slug for c in robadors.categories] == ["jazz"]
    # All nine cinema venues are single-category film.
    for slug in ("filmoteca", "cines-verdi", "renoir-floridablanca", "phenomena",
                 "zumzeig", "cinema-malda", "sala-montjuic", "cinemes-girona", "espai-texas"):
        v = session.query(Venue).filter_by(slug=slug).one()
        assert [c.slug for c in v.categories] == ["film"]


def test_classical_venues_categories(session):
    seed(session)
    # Multi-category classical venues.
    palau = session.query(Venue).filter_by(slug="palau-musica").one()
    assert sorted(c.slug for c in palau.categories) == ["classical", "flamenco", "jazz"]
    for slug in ("auditori", "meam"):
        v = session.query(Venue).filter_by(slug=slug).one()
        assert sorted(c.slug for c in v.categories) == ["classical", "jazz"]
    # Single-category classical venues.
    for slug in ("santa-maria-del-mar", "santa-maria-del-pi", "ateneu-barcelones", "generalitat-carillo"):
        v = session.query(Venue).filter_by(slug=slug).one()
        assert [c.slug for c in v.categories] == ["classical"]
    # Liceu spans the opera house's strands.
    liceu = session.query(Venue).filter_by(slug="liceu").one()
    assert sorted(c.slug for c in liceu.categories) == ["classical", "dance", "kids", "pop"]


def test_liceu_splits_into_classical_dance_kids_pop_lists(session):
    seed(session)
    liceu = session.query(Venue).filter_by(slug="liceu").one()
    for list_slug, cat_slug in (("classical", "classical"), ("dance", "dance"),
                                ("kids", "kids"), ("pop", "pop")):
        lst = session.query(List).filter_by(slug=list_slug).one()
        cat = session.query(Category).filter_by(slug=cat_slug).one()
        mem = session.query(ListVenue).filter_by(list_id=lst.id, venue_id=liceu.id).one()
        assert mem.whitelist_category_id == cat.id


def test_palau_splits_into_classical_jazz_flamenco_lists(session):
    seed(session)
    palau = session.query(Venue).filter_by(slug="palau-musica").one()
    for list_slug, cat_slug in (("classical", "classical"), ("jazz", "jazz"), ("flamenco", "flamenco")):
        lst = session.query(List).filter_by(slug=list_slug).one()
        cat = session.query(Category).filter_by(slug=cat_slug).one()
        mem = session.query(ListVenue).filter_by(list_id=lst.id, venue_id=palau.id).one()
        assert mem.whitelist_category_id == cat.id


def test_sala_beckett_splits_into_theater_jazz_lists(session):
    seed(session)
    beckett = session.query(Venue).filter_by(slug="sala-beckett").one()
    assert sorted(c.slug for c in beckett.categories) == ["jazz", "theater"]
    for list_slug, cat_slug in (("theater", "theater"), ("jazz", "jazz")):
        lst = session.query(List).filter_by(slug=list_slug).one()
        cat = session.query(Category).filter_by(slug=cat_slug).one()
        mem = session.query(ListVenue).filter_by(list_id=lst.id, venue_id=beckett.id).one()
        assert mem.whitelist_category_id == cat.id


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
    film_list = session.query(List).filter_by(slug="film").one()
    classical_list = session.query(List).filter_by(slug="classical").one()
    cinema_memberships = [(slug, film_list) for slug in
                          ("filmoteca", "cines-verdi", "renoir-floridablanca", "phenomena",
                           "zumzeig", "cinema-malda", "sala-montjuic", "cinemes-girona", "espai-texas")]
    classical_memberships = [(slug, classical_list) for slug in
                             ("santa-maria-del-mar", "santa-maria-del-pi",
                              "ateneu-barcelones", "generalitat-carillo")]
    for venue_slug, lst in [("harlem-jazz-club", jazz_list),
                            ("robadors", jazz_list)] + cinema_memberships + classical_memberships:
        v = session.query(Venue).filter_by(slug=venue_slug).one()
        mem = session.query(ListVenue).filter_by(list_id=lst.id, venue_id=v.id).one()
        assert mem.whitelist_category_id is None
