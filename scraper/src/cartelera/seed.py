from __future__ import annotations
from sqlalchemy.orm import Session
from cartelera.models import City, Category, Venue, List, ListVenue
from cartelera.scrapers import REGISTRY
from cartelera.types import VenueDefinition
# Importing each scraper module runs its register(...) call (populates REGISTRY).
import cartelera.scrapers.jamboree  # noqa: F401
import cartelera.scrapers.harlem_jazz_club  # noqa: F401
import cartelera.scrapers.robadors  # noqa: F401
import cartelera.scrapers.casa_figari  # noqa: F401
import cartelera.scrapers.sala_beckett  # noqa: F401
import cartelera.scrapers.big_bang  # noqa: F401
import cartelera.scrapers.filmoteca  # noqa: F401
import cartelera.scrapers.cines_verdi  # noqa: F401
import cartelera.scrapers.renoir_floridablanca  # noqa: F401
import cartelera.scrapers.phenomena  # noqa: F401
import cartelera.scrapers.zumzeig  # noqa: F401
import cartelera.scrapers.cinema_malda  # noqa: F401
import cartelera.scrapers.sala_montjuic  # noqa: F401
import cartelera.scrapers.cinemes_girona  # noqa: F401
import cartelera.scrapers.espai_texas  # noqa: F401
import cartelera.scrapers.palau_musica  # noqa: F401
import cartelera.scrapers.auditori  # noqa: F401
import cartelera.scrapers.meam  # noqa: F401
import cartelera.scrapers.santa_maria_del_mar  # noqa: F401
import cartelera.scrapers.santa_maria_del_pi  # noqa: F401
import cartelera.scrapers.ateneu_barcelones  # noqa: F401
import cartelera.scrapers.generalitat_carillo  # noqa: F401
import cartelera.scrapers.liceu  # noqa: F401

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
    lst = session.query(List).filter_by(slug=slug).one_or_none()
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
        venue = Venue(slug=defn.slug, name=defn.name, city_id=city_id, address=defn.address, site_url=defn.site_url)
        session.add(venue)
        session.flush()
    else:
        venue.name = defn.name
        venue.address = defn.address
        venue.site_url = defn.site_url
    venue.categories = [cats[s] for s in defn.category_slugs if s in cats]
    for membership in defn.list_memberships:
        lst = _get_or_create_list(session, membership.list_slug, city_id)
        whitelist_id = cats[membership.whitelist_category_slug].id if membership.whitelist_category_slug else None
        _ensure_membership(session, lst.id, venue.id, whitelist_id)


def seed(session: Session) -> None:
    """Idempotent seed: ensures city, categories, and all registered venues exist."""
    bcn = _get_or_create_city(session, "barcelona", "Barcelona")
    cats = {slug: _get_or_create_category(session, slug, name) for slug, name in CATEGORIES}
    for _scraper, venue_def in REGISTRY.values():
        _upsert_venue(session, venue_def, bcn.id, cats)
    session.commit()
