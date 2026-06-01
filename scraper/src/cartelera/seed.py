from __future__ import annotations
from sqlalchemy.orm import Session
from cartelera.models import City, Category, Venue, List, ListVenue

CATEGORIES = [
    ("film", "Film"),
    ("jazz", "Jazz"),
    ("classical", "Classical"),
    ("theater", "Theater"),
    ("club", "Club"),
]


def _get_or_create_list(session: Session, slug: str, name: str, city_id: int) -> List:
    lst = session.query(List).filter_by(slug=slug).one_or_none()
    if not lst:
        lst = List(slug=slug, name=name, author="cartelera", city_id=city_id)
        session.add(lst)
        session.flush()
    return lst


def _ensure_membership(session: Session, list_id: int, venue_id: int, whitelist_category_id: int | None) -> None:
    existing = session.query(ListVenue).filter_by(
        list_id=list_id, venue_id=venue_id, whitelist_category_id=whitelist_category_id
    ).one_or_none()
    if not existing:
        session.add(ListVenue(list_id=list_id, venue_id=venue_id,
                              whitelist_category_id=whitelist_category_id))


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

    # Jamboree is a multi-category venue: jazz concerts + club (+18 DJ) nights.
    jamboree = session.query(Venue).filter_by(slug="jamboree").one_or_none()
    if not jamboree:
        jamboree = Venue(
            slug="jamboree", name="Jamboree", city_id=bcn.id,
            address="Plaça Reial, 17, 08002 Barcelona",
            site_url="https://jamboreejazz.com",
        )
        session.add(jamboree)
        session.flush()
    # Keep the venue's category set current (idempotent).
    jamboree.categories = [cats["jazz"], cats["club"]]

    # cartelera-authored category lists. Jamboree is in both the jazz and club
    # lists, each membership whitelisted to that category so a multi-category
    # venue's events land in the right list.
    jazz_list = _get_or_create_list(session, "jazz", "Jazz", bcn.id)
    _ensure_membership(session, jazz_list.id, jamboree.id, cats["jazz"].id)

    club_list = _get_or_create_list(session, "club", "Club", bcn.id)
    _ensure_membership(session, club_list.id, jamboree.id, cats["club"].id)

    session.commit()
