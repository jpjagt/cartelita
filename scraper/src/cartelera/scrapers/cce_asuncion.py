"""Centro Cultural de España Juan de Salazar (CCE Asunción) — film cycles and
performing arts in its auditorium (Herrera 834).

Reads the AECID-network agenda through the shared `_aecid` module; this file
only holds the centre's curation (see cce_asuncion_SOURCE.md): the agenda's
own category labels decide what is programme, the structured "Lugar" field
whether it happens at the centre.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from cartelera.scrapers import _aecid, register
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

SITE_URL = "https://cceasuncion.aecid.es"
VENUE_SLUG = "cce-asuncion"
TZ = ZoneInfo("America/Asuncion")

CONFIG = _aecid.AecidConfig(
    site=SITE_URL,
    venue_slug=VENUE_SLUG,
    # The agenda's labels → our categories. "Escénicas" (performing arts) is
    # the agenda's one stage label; it covers theatre, dance and clown alike,
    # with no finer label to tell them apart.
    programme={"Cine / Audiovisual": "film", "Escénicas": "theater"},
    # Courses/workshops and exhibitions, whatever else they're labelled.
    non_programme=frozenset({"Formación", "Exposiciones"}),
    extra={"Infantil / Juvenil": "kids"},
    own_place_markers=("Centro Cultural de España", "CCE"),
)


class CceAsuncionScraper:
    venue_slug = VENUE_SLUG

    def scrape(self, today: dt.date | None = None) -> list[ScrapedEvent]:
        return _aecid.scrape(CONFIG, today or dt.datetime.now(TZ).date())


register(
    scraper=CceAsuncionScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Centro Cultural de España Juan de Salazar",
        city_slug="asuncion",
        address="Herrera 834, Asunción",
        site_url=SITE_URL,
        instagram_url="https://www.instagram.com/cceasuncion",
        category_slugs=["film", "theater", "kids"],
        list_memberships=[
            ListMembership(list_slug="film", whitelist_category_slug="film"),
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
