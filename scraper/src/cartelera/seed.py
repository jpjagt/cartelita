from __future__ import annotations
from sqlalchemy.orm import Session
from cartelera.models import City, Category, Venue, List, ListVenue
from cartelera.scrapers import REGISTRY, load_all
from cartelera.types import VenueDefinition

# Every city Cartelita runs in. A venue definition whose city_slug isn't here
# fails fast in seed() — add the city deliberately, not by side effect.
CITIES = [
    ("barcelona", "Barcelona"),
    ("yerevan", "Yerevan"),
    ("amsterdam", "Amsterdam"),
]

# Categories are global (shared across cities); lists are per-city, created
# lazily from venue list_memberships — so a city simply never gets lists for
# categories none of its venues program.
CATEGORIES = [
    ("film", "Film"),
    ("jazz", "Jazz"),
    ("classical", "Classical"),
    ("theater", "Theater"),
    ("club", "Club"),
    ("flamenco", "Flamenco"),
    ("dance", "Dance"),
    ("kids", "Kids"),
    ("pop", "Pop"),
    ("folk", "Folk"),
    ("rock", "Rock"),
    ("alternative", "Alternative"),
]


def _get_or_create_city(session: Session, slug: str, name: str) -> City:
    city = session.query(City).filter_by(slug=slug).one_or_none()
    if not city:
        city = City(slug=slug, name=name)
        session.add(city)
        session.flush()
    return city


def _get_or_create_category(session: Session, slug: str, name: str) -> Category:
    cat = session.query(Category).filter_by(slug=slug).one_or_none()
    if not cat:
        cat = Category(slug=slug, name=name)
        session.add(cat)
        session.flush()
    return cat


def _get_or_create_list(session: Session, slug: str, city_id: int) -> List:
    # List slugs are unique per city (every city has its own "jazz").
    lst = session.query(List).filter_by(slug=slug, city_id=city_id).one_or_none()
    if not lst:
        lst = List(slug=slug, name=slug.capitalize(), author="cartelera", city_id=city_id)
        session.add(lst)
        session.flush()
    return lst


def _ensure_membership(
    session: Session, list_id: int, venue_id: int, whitelist_category_id: int | None
) -> None:
    existing = (
        session.query(ListVenue)
        .filter_by(list_id=list_id, venue_id=venue_id, whitelist_category_id=whitelist_category_id)
        .one_or_none()
    )
    if not existing:
        session.add(ListVenue(list_id=list_id, venue_id=venue_id, whitelist_category_id=whitelist_category_id))


def _upsert_venue(session: Session, defn: VenueDefinition, city_id: int, cats: dict[str, Category]) -> None:
    venue = session.query(Venue).filter_by(slug=defn.slug).one_or_none()
    if not venue:
        venue = Venue(slug=defn.slug, name=defn.name, city_id=city_id, address=defn.address,
                      site_url=defn.site_url, instagram_url=defn.instagram_url)
        session.add(venue)
        session.flush()
    else:
        venue.name = defn.name
        venue.address = defn.address
        venue.site_url = defn.site_url
        venue.instagram_url = defn.instagram_url
    venue.categories = [cats[s] for s in defn.category_slugs if s in cats]
    for membership in defn.list_memberships:
        lst = _get_or_create_list(session, membership.list_slug, city_id)
        whitelist_id = cats[membership.whitelist_category_slug].id if membership.whitelist_category_slug else None
        _ensure_membership(session, lst.id, venue.id, whitelist_id)


def seed(session: Session) -> None:
    """Idempotent seed: ensures cities, categories, and all registered venues exist."""
    load_all()
    cities = {slug: _get_or_create_city(session, slug, name) for slug, name in CITIES}
    cats = {slug: _get_or_create_category(session, slug, name) for slug, name in CATEGORIES}
    for _scraper, source in REGISTRY.values():
        for venue_def in source.venues:
            city = cities.get(venue_def.city_slug)
            if city is None:
                raise ValueError(
                    f"unknown city slug {venue_def.city_slug!r} for venue "
                    f"{venue_def.slug!r}; add it to seed.CITIES"
                )
            _upsert_venue(session, venue_def, city.id, cats)
    session.commit()
