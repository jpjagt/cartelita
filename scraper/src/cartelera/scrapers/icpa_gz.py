"""ICPA – Goethe-Zentrum (Instituto Cultural Paraguayo-Alemán, Asunción).

WordPress + The Events Calendar: we read its REST API through the shared
`_tribe_events` helper (see icpa_gz_SOURCE.md). The calendar mixes the
institute's cultural programme (film cycles, concerts, dance) with courses,
workshops, talks, reading clubs, exams and off-site partner events. Curation
uses the calendar's own structure only:

- the event's Tribe **venue** must be one of the institute's own rooms (its
  name contains "Instituto Cultural Paraguayo-Alemán": the main building,
  Salón Rolando Rasmussen, Biblioteca Ulrich Schmidl) — partner events at
  other venues (cinemas, schools, the Teatro Municipal, Online) are dropped;
- the event needs a **programme label** among its event categories (Cine &
  its cycles → film, Concierto → classical, Danza → dance, Teatro → theater)
  and **no non-programme label** (Taller, Charla, Exposición, Convocatoria …).
"""

from __future__ import annotations

import re

from cartelera.scrapers import _tribe_events as tribe
from cartelera.scrapers import register
from cartelera.scrapers.price import format_pyg
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

SITE_URL = "https://www.icpa-gz.org.py"
VENUE_SLUG = "icpa-gz"
# The institute's own rooms all carry this in their Tribe venue name.
OWN_VENUE_MARKER = "Instituto Cultural Paraguayo-Alemán"

# The calendar's programme labels → our categories.
PROGRAMME: dict[str, str] = {
    "Cine": "film",
    "Haus-Kino | Cine": "film",
    "Ciclos de Cine Alemán": "film",
    "Ciclo de Cine Europeo en Paraguay": "film",
    # The institute's "Concierto" label covers its chamber/guitar/choir
    # recitals in the Salón Rolando Rasmussen; no finer genre label exists.
    "Concierto": "classical",
    "Danza": "dance",
    "Teatro": "theater",
}
KIDS_LABEL = "Evento para niñas y niños"
# Labels that mark an item as not programme, whatever else it carries:
# workshops/courses, talks, exhibitions, calls, exams, fairs, online items.
NON_PROGRAMME = {
    "Taller",
    "Capacitación",
    "Formación profesional",
    "Charla",
    "Conferencia",
    "Conversatorio",
    "Exposición",
    "Convocatoria",
    "Concurso",
    "Beca",
    "Exámenes internacionales",
    "Estudiar en Alemania",
    "Feria",
    "Feria Al Parque",
    "Mercadillo navideño",
    "Evento digital",
    "Goethe on Demand",
    "Presentación",
    "Presentación del libro",
    "Deporte",
}
# Labels that say nothing about the item's kind (kept out of annotations).
NEUTRAL = {"Arte", "Cultura", "Evento presencial", "Eventos", "apoyado por el ICPA-GZ"}

_FREE = re.compile(r"\b(gratuit[oa]|gratis|libre)\b", re.IGNORECASE)


def venue_name(ev: dict) -> str:
    venue = ev.get("venue")
    return tribe.text(venue.get("venue")) if isinstance(venue, dict) else ""


def at_own_venue(ev: dict) -> bool:
    return OWN_VENUE_MARKER in venue_name(ev).replace("–", "-")


def categorize(labels: list[str]) -> list[str]:
    """Our categories for a programme item, or [] when it isn't one."""
    if set(labels) & NON_PROGRAMME:
        return []
    cats = list(dict.fromkeys(PROGRAMME[l] for l in labels if l in PROGRAMME))
    if cats and KIDS_LABEL in labels:
        cats.append("kids")
    return cats


def price(ev: dict) -> str | None:
    """Tribe cost in guaraníes: `cost_details.values` ("300.000", "40000",
    "0") → the highest, house format; "Gratuito" → free."""
    values: list[int] = []
    for v in (ev.get("cost_details") or {}).get("values") or []:
        digits = str(v).replace(".", "").strip()
        if digits.isdigit():
            values.append(int(digits))
    if values:
        return format_pyg(max(values))
    cost = tribe.text(ev.get("cost"))
    if _FREE.search(cost):
        return "free"
    return None


def parse_events(raw: list[dict]) -> list[ScrapedEvent]:
    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for ev in raw:
        title = tribe.title(ev)
        if not title or not ev.get("url") or not at_own_venue(ev):
            continue
        labels = tribe.category_names(ev)
        cats = categorize(labels)
        if not cats:
            continue
        external_id = str(ev["id"])
        if external_id in seen:
            continue
        seen.add(external_id)
        start_date, start_time = tribe.start(ev)
        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=ev["url"],
                category_slugs=cats,
                price=price(ev),
                description=tribe.text(ev.get("excerpt")) or None,
                image_url=tribe.image_url(ev),
                external_id=external_id,
                annotations=[
                    l for l in labels
                    if l not in NEUTRAL and l not in PROGRAMME and l != KIDS_LABEL
                ],
            )
        )
    return events


class IcpaGzScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        return parse_events(tribe.fetch_all(SITE_URL))


register(
    scraper=IcpaGzScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="ICPA – Goethe-Zentrum",
        city_slug="asuncion",
        address="Juan de Salazar 310 esq. Artigas, Asunción",
        site_url=SITE_URL,
        instagram_url="https://www.instagram.com/icpa_gz",
        category_slugs=["film", "classical", "dance", "theater", "kids"],
        list_memberships=[
            ListMembership(list_slug="film", whitelist_category_slug="film"),
            ListMembership(list_slug="classical", whitelist_category_slug="classical"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
