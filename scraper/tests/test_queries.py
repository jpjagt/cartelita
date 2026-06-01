import datetime as dt
from cartelera.seed import seed
from cartelera.upsert import upsert_venue_events
from cartelera.queries import events_for_list
from cartelera.types import ScrapedEvent
from cartelera.models import City, Venue, Category, List, ListVenue


def _se(eid, d, t=None, cats=("jazz",)):
    return ScrapedEvent(title=f"E{eid}", start_date=d, start_time=t,
                        source_url=f"https://x/{eid}", category_slugs=list(cats), external_id=eid)


def test_list_returns_chronological_future_events(session):
    seed(session)
    upsert_venue_events(session, "jamboree", [
        _se("a", dt.date(2026, 6, 9), dt.time(21, 0)),
        _se("b", dt.date(2026, 6, 2), dt.time(19, 0)),
        _se("c", dt.date(2026, 6, 2), dt.time(22, 0)),
        _se("past", dt.date(2026, 5, 1)),
    ])
    session.commit()
    evs = events_for_list(session, "jazz", on_or_after=dt.date(2026, 6, 1))
    # chronological: date then time -> Eb (6/2 19:00), Ec (6/2 22:00), Ea (6/9 21:00)
    assert [e.title for e in evs] == ["Eb", "Ec", "Ea"]
    # past event excluded
    assert all(e.start_date >= dt.date(2026, 6, 1) for e in evs)


def test_per_venue_whitelist_filters_to_one_category(session):
    """A multi-category venue in a list with a film whitelist shows only its film
    events, not its expo events. This is the core multi-category separability."""
    seed(session)
    # Build a multi-category venue (film + theater) and a 'film' list whitelisting film.
    bcn = session.query(City).filter_by(slug="barcelona").one()
    film = session.query(Category).filter_by(slug="film").one()
    theater = session.query(Category).filter_by(slug="theater").one()
    filmoteca = Venue(slug="filmoteca", name="Filmoteca", city_id=bcn.id,
                      categories=[film, theater])
    session.add(filmoteca)
    film_list = List(slug="film", name="Film", author="cartelera", city_id=bcn.id)
    session.add(film_list)
    session.flush()
    session.add(ListVenue(list_id=film_list.id, venue_id=filmoteca.id,
                          whitelist_category_id=film.id))
    session.commit()

    upsert_venue_events(session, "filmoteca", [
        _se("film1", dt.date(2026, 6, 3), cats=("film",)),
        _se("play1", dt.date(2026, 6, 4), cats=("theater",)),
    ])
    session.commit()

    evs = events_for_list(session, "film", on_or_after=dt.date(2026, 6, 1))
    titles = [e.title for e in evs]
    assert titles == ["Efilm1"]  # the theater event is excluded by the whitelist


def test_null_whitelist_includes_all_venue_events(session):
    """The jazz list's jamboree membership has NULL whitelist -> all events show."""
    seed(session)
    upsert_venue_events(session, "jamboree", [
        _se("x", dt.date(2026, 6, 5)),
        _se("y", dt.date(2026, 6, 6)),
    ])
    session.commit()
    evs = events_for_list(session, "jazz", on_or_after=dt.date(2026, 6, 1))
    assert len(evs) == 2
