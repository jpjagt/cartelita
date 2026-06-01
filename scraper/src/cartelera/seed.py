from __future__ import annotations
from sqlalchemy.orm import Session
from cartelera.models import City, Category, Venue, List, ListVenue

CATEGORIES = [("film", "Film"), ("jazz", "Jazz"), ("classical", "Classical"), ("theater", "Theater")]


def seed(session: Session) -> None:
    """Idempotent seed of launch reference data for Barcelona."""
    bcn = session.query(City).filter_by(slug="barcelona").one_or_none()
    if not bcn:
        bcn = City(slug="barcelona", name="Barcelona")
        session.add(bcn)
        session.flush()

    cats: dict[str, Category] = {}
    for slug, name in CATEGORIES:
        c = session.query(Category).filter_by(slug=slug).one_or_none()
        if not c:
            c = Category(slug=slug, name=name)
            session.add(c)
            session.flush()
        cats[slug] = c

    jamboree = session.query(Venue).filter_by(slug="jamboree").one_or_none()
    if not jamboree:
        jamboree = Venue(
            slug="jamboree", name="Jamboree", city_id=bcn.id,
            address="Plaça Reial, 17, 08002 Barcelona",
            site_url="https://jamboreejazz.com",
            categories=[cats["jazz"]],
        )
        session.add(jamboree)
        session.flush()

    # cartelera-authored jazz list: jazz venues, no whitelist needed (single-cat).
    jazz_list = session.query(List).filter_by(slug="jazz").one_or_none()
    if not jazz_list:
        jazz_list = List(slug="jazz", name="Jazz", author="cartelera", city_id=bcn.id)
        session.add(jazz_list)
        session.flush()
    membership = session.query(ListVenue).filter_by(
        list_id=jazz_list.id, venue_id=jamboree.id, whitelist_category_id=None
    ).one_or_none()
    if not membership:
        session.add(ListVenue(list_id=jazz_list.id, venue_id=jamboree.id, whitelist_category_id=None))
    session.commit()
