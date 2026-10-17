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
    ("rotterdam", "Rotterdam"),
    ("utrecht", "Utrecht"),
    ("asuncion", "Asunción"),
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


def _forget_coordinates(venue: Venue) -> None:
    """Clear a venue's geocoded position so the next geocode pass looks it up
    again (its address changed)."""
    venue.lat = venue.lng = venue.geocoded_at = None


def _upsert_venue(
    session: Session, defn: VenueDefinition, city_id: int, cats: dict[str, Category],
    *, keep_extra_categories: bool = False,
) -> None:
    """Create/update a code-defined venue. Its categories become exactly the
    code-defined ones — unless `keep_extra_categories` (its source extends
    venue categories at run time): then code's are the minimum and categories
    a run added are kept. List memberships are only ever added."""
    venue = session.query(Venue).filter_by(slug=defn.slug).one_or_none()
    if not venue:
        venue = Venue(slug=defn.slug, name=defn.name, city_id=city_id, address=defn.address,
                      site_url=defn.site_url, instagram_url=defn.instagram_url)
        session.add(venue)
        session.flush()
    else:
        if venue.address != defn.address and defn.lat is None:
            _forget_coordinates(venue)  # moved: geocode the new address
        venue.name = defn.name
        venue.address = defn.address
        venue.site_url = defn.site_url
        venue.instagram_url = defn.instagram_url
    if defn.lat is not None:
        # Explicit coordinates win; geocoding skips code-defined venues that
        # carry them. geocoded_at stays NULL, so dropping them from the
        # definition later makes the next geocode pass look the venue up.
        venue.lat, venue.lng, venue.geocoded_at = defn.lat, defn.lng, None
    code = [cats[s] for s in defn.category_slugs if s in cats]
    extra = ([c for c in venue.categories if c.slug not in defn.category_slugs]
             if keep_extra_categories else [])
    venue.categories = code + extra
    for membership in defn.list_memberships:
        lst = _get_or_create_list(session, membership.list_slug, city_id)
        whitelist_id = cats[membership.whitelist_category_slug].id if membership.whitelist_category_slug else None
        _ensure_membership(session, lst.id, venue.id, whitelist_id)


def extend_venue_categories(session: Session, venue: Venue, category_slugs: list[str]) -> list[str]:
    """Add the categories `venue` doesn't have yet, each with a list membership
    whitelisted to it (the category's list in the venue's city). Never removes
    anything. Returns the slugs added, in the given order. Runs in the
    caller's transaction (see SourceDefinition.extends_venue_categories)."""
    have = {c.slug for c in venue.categories}
    new = list(dict.fromkeys(s for s in category_slugs if s not in have))
    if not new:
        return []
    cats = {c.slug: c for c in session.query(Category).filter(Category.slug.in_(new))}
    if unknown := [s for s in new if s not in cats]:
        raise ValueError(f"unknown category slug {unknown[0]!r} for venue {venue.slug!r}; "
                         "add it to seed.CATEGORIES")
    venue.categories = list(venue.categories) + [cats[s] for s in new]
    for s in new:
        lst = _get_or_create_list(session, s, venue.city_id)
        _ensure_membership(session, lst.id, venue.id, cats[s].id)
    session.flush()
    return new


def upsert_discovered_venue(session: Session, source_slug: str, defn: VenueDefinition) -> bool:
    """Create or grow a venue a source discovered at run time (see
    cartelera.discovery). Returns True when the venue was created.

    Created once, with `discovered_by = source_slug`; afterwards only grows:
    new categories and list memberships are added (never removed), and an
    address is filled in if it had none. Runs in the caller's transaction.
    The caller has checked the slug isn't owned by anything else."""
    city = session.query(City).filter_by(slug=defn.city_slug).one_or_none()
    if city is None:
        raise ValueError(f"unknown city slug {defn.city_slug!r} for discovered venue "
                         f"{defn.slug!r}; add it to seed.CITIES")
    cats = {c.slug: c for c in session.query(Category)}
    wanted = set(defn.category_slugs) | {
        m.whitelist_category_slug for m in defn.list_memberships if m.whitelist_category_slug}
    if unknown := sorted(wanted - set(cats)):
        raise ValueError(f"unknown category slug {unknown[0]!r} for discovered venue "
                         f"{defn.slug!r}; add it to seed.CATEGORIES")
    venue = session.query(Venue).filter_by(slug=defn.slug).one_or_none()
    created = venue is None
    if created:
        venue = Venue(slug=defn.slug, name=defn.name, city_id=city.id, address=defn.address,
                      site_url=defn.site_url, instagram_url=defn.instagram_url,
                      discovered_by=source_slug)
        session.add(venue)
        session.flush()
    elif venue.address is None and defn.address:
        venue.address = defn.address
        _forget_coordinates(venue)  # retry geocoding with the address
    have = {c.slug for c in venue.categories}
    venue.categories = list(venue.categories) + [
        cats[s] for s in defn.category_slugs if s not in have]
    for membership in defn.list_memberships:
        lst = _get_or_create_list(session, membership.list_slug, venue.city_id)
        whitelist_id = cats[membership.whitelist_category_slug].id if membership.whitelist_category_slug else None
        _ensure_membership(session, lst.id, venue.id, whitelist_id)
    session.flush()
    return created


def seed(session: Session) -> None:
    """Idempotent seed: ensures cities, categories, and all registered venues
    exist. Venues a source discovers at run time are created by `cartelera
    run` (upsert_discovered_venue), not here; they persist between runs."""
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
            _upsert_venue(session, venue_def, city.id, cats,
                          keep_extra_categories=source.extends_venue_categories)
    session.commit()
