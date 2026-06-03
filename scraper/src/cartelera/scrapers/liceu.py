from __future__ import annotations
import datetime as dt
import json
from zoneinfo import ZoneInfo

import httpx

from cartelera.scrapers import register
from cartelera.types import (
    ScrapedEvent,
    ScrapedTranslation,
    VenueDefinition,
    ListMembership,
)

# Gran Teatre del Liceu — Barcelona's opera house. The programme page
# (/ca/programacio?view=itemsListView) is a Drupal site that renders its listing
# client-side via programationViewLiceu.js, which fetches a single clean static
# JSON document. We hit that JSON directly (no browser): it carries multilingual
# title/subtitle/url, the venue taxonomy, the main image, and one session row per
# occurrence. Price is NOT in the feed (it lives only on detail pages) → None.
# See liceu_SOURCE.md.
VENUE_SLUG = "liceu"
BASE_URL = "https://www.liceubarcelona.cat"
PROGRAMME_JSON_URL = "https://liceubarcelona.cat/sites/default/files/programme.json"

TZ = ZoneInfo("Europe/Madrid")

# The feed's session timestamps are systematically 2h behind the wall-clock the
# venue displays (verified against detail pages + the 535-session hour
# distribution — see liceu_SOURCE.md "Timestamp quirk"). Correct by +2h.
_TIME_OFFSET = dt.timedelta(hours=2)

KNOWN_CATEGORIES = {"classical", "dance", "kids", "pop"}

# Category discriminator: the production's taxonomy labels (the `ca` strings).
# A production may carry several; the first rule that matches wins, so the genre
# that best describes the event takes precedence over the classical default.
# Cross-cutting audience/series tags (LiceUnder35, Liceu de les arts) are NOT
# genres — they never decide the category and are surfaced as annotations.
_CATEGORY_RULES: list[tuple[set[str], str]] = [
    ({"Dansa"}, "dance"),
    ({"Petit Liceu", "LiceuAprèn"}, "kids"),
    ({"Promotores externes"}, "pop"),
]
DEFAULT_CATEGORY = "classical"
# Taxonomy labels that are audience/series tags, not genres — annotations only.
_NON_GENRE_TAGS = {"LiceUnder35", "Liceu de les arts"}


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    out = text.strip()
    return out or None


def _category_for(categories: dict) -> str:
    """Map a production's taxonomy labels (the `ca` strings, as dict keys) to one
    of our category slugs by priority. `categories` is any iterable of label
    strings (tests pass a {label: _} dict; the parser passes the same)."""
    labels = set(categories)
    for triggers, slug in _CATEGORY_RULES:
        if labels & triggers:
            return slug
    return DEFAULT_CATEGORY


def _labels_ca(production: dict) -> list[str]:
    """The production's taxonomy labels in Catalan, order-preserving."""
    out: list[str] = []
    for entry in (production.get("categories") or {}).values():
        label = _clean((entry or {}).get("ca"))
        if label and label not in out:
            out.append(label)
    return out


def _abs_url(path: str | None) -> str | None:
    path = _clean(path)
    if not path:
        return None
    if path.startswith("http"):
        return path
    return f"{BASE_URL}{path}"


def _translations(production: dict, category: str) -> list[ScrapedTranslation]:
    """es/en content from the multilingual feed (ca is the canonical event)."""
    titles = production.get("title") or {}
    subtitles = production.get("subtitle") or {}
    urls = production.get("url") or {}
    out: list[ScrapedTranslation] = []
    for lang in ("es", "en"):
        title = _clean(titles.get(lang))
        if not title:
            continue
        out.append(
            ScrapedTranslation(
                lang=lang,
                title=title,
                description=_clean(subtitles.get(lang)),
                source_url=_abs_url(urls.get(lang)),
            )
        )
    return out


def parse_programme(json_text: str, today: dt.date | None = None) -> list[ScrapedEvent]:
    """Parse the Liceu programme JSON into one ScrapedEvent per upcoming session.

    The feed mixes seasons, so each session is filtered to `today`-or-later
    (defaults to the real today). Session timestamps get the +2h correction.
    Category comes from the production's taxonomy; price is None (not in feed).
    """
    if today is None:
        today = dt.datetime.now(TZ).date()
    data = json.loads(json_text)
    productions = data.get("productions", {})

    events: list[ScrapedEvent] = []
    for production in productions.values():
        title = _clean((production.get("title") or {}).get("ca"))
        url = _abs_url((production.get("url") or {}).get("ca"))
        if not title or not url:
            continue

        labels = _labels_ca(production)
        category = _category_for(labels)
        image_url = _abs_url(production.get("main_image"))
        subtitle = _clean((production.get("subtitle") or {}).get("ca"))
        translations = _translations(production, category)

        # Annotations: subtitle + the non-genre audience/series tags. Genre labels
        # that drove the category are not repeated; category slugs never leak in.
        base_annotations: list[str] = []
        if subtitle:
            base_annotations.append(subtitle)
        base_annotations.extend(t for t in labels if t in _NON_GENRE_TAGS)

        for session in production.get("sessions") or []:
            ts = session.get("date")
            sid = session.get("id")
            if ts is None or sid is None:
                continue
            start = dt.datetime.fromtimestamp(int(ts), TZ) + _TIME_OFFSET
            if start.date() < today:
                continue

            # The subscription turn (e.g. "Abonament E") is per-session context.
            annotations = list(base_annotations)
            for turn in session.get("turns") or []:
                turn_name = _clean((turn.get("name") or {}).get("ca"))
                if turn_name and turn_name not in annotations:
                    annotations.append(turn_name)

            start_time = start.time()
            events.append(
                ScrapedEvent(
                    title=title,
                    start_date=start.date(),
                    start_time=start_time,
                    start_times=[start_time],
                    source_url=url,
                    category_slugs=[category],
                    price=None,  # not in the feed (see SOURCE.md)
                    description=subtitle,
                    image_url=image_url,
                    external_id=f"liceu-session-{sid}",
                    annotations=annotations,
                    translations=translations,
                )
            )
    return events


class LiceuScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        json_text = httpx.get(PROGRAMME_JSON_URL, follow_redirects=True, timeout=60).text
        return parse_programme(json_text)


register(
    scraper=LiceuScraper(),
    venue=VenueDefinition(
        slug="liceu",
        name="Gran Teatre del Liceu",
        city_slug="barcelona",
        address="La Rambla, 51-59, 08002 Barcelona",
        site_url="https://www.liceubarcelona.cat",
        category_slugs=["classical", "dance", "kids", "pop"],
        list_memberships=[
            ListMembership(list_slug="classical", whitelist_category_slug="classical"),
            ListMembership(list_slug="dance", whitelist_category_slug="dance"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
            ListMembership(list_slug="pop", whitelist_category_slug="pop"),
        ],
    ),
)
