from __future__ import annotations
import datetime as dt
import json
import re

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.scrapers.price import format_eur_range
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Palau de la Música Catalana runs a woost/cocktail CMS. The programme page
# (/ca/programacio_1158636) renders its concert listing client-side via
# sessionlisting.js, which fetches a single clean JSON document. We hit that JSON
# endpoint directly — it is the most complete and robust source (it carries title,
# subtitle, price, the gratis flag, hashtags, cycles, image, and one session row
# per occurrence with an ISO-ish start datetime). See palau_musica_SOURCE.md.
PROGRAMMING_JSON_URL = (
    "https://www.palaumusica.cat/ca/programming_data_json"
    "?palau_productions=1&orfeo_productions=0&espaisoci_productions=0&sessions_as_dict=1"
)
BASE_URL = "https://www.palaumusica.cat"
VENUE_SLUG = "palau-musica"

DEFAULT_CATEGORY = "classical"
# Per-event category override driven by the production's hashtags. The Palau
# programmes the Barcelona Jazz Festival (#jazz) and flamenco galas / "De Cajón!"
# (#flamenc); everything else is classical. #cinema (film-with-live-orchestra) and
# #conferències have no top-level category yet — they fall back to classical and
# are surfaced in annotations (see SOURCE.md).
HASHTAG_CATEGORY = {"jazz": "jazz", "flamenc": "flamenco"}

# Palau venues (anything else is an off-site collaboration we annotate with the stage).
_PALAU_STAGES = {
    "Sala de Concerts",
    "Sala Petit Palau",
    "Sala d'Assaig de l'Orfeó Català",
    "Sala d'Assaig de l'Orfeó Català (inici)",
}

# Price tiers after any of these markers are member/discount/secondary prices we drop.
_PRICE_TIER_CUT = re.compile(
    r"\(|/|socis|abonats|palau jove|aula palau|especial|discapacitat|anticipada|general",
    re.IGNORECASE,
)
_FREE_MARKERS = re.compile(
    r"gratu[ïi]?t|acc[ée]s lliure|entrada lliure|\blliure\b", re.IGNORECASE
)
_PRICE_NUM = re.compile(r"(\d+)(?:[.,]\d+)?")


def _strip_html(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    return cleaned or None


def _parse_price(raw: str | None, gratis: bool) -> str | None:
    """Normalize the Palau's free-text price to the project convention.

    "de 18 a 68 €" -> "18–68€" style range (only when high >= 2× low; minor
    spreads like "de 36 a 64 €" collapse to "64€" per format_eur_range);
    "32 €"/"32"/"20.0" -> "32€"; gratis flag or a gratuït/lliure phrase -> "free";
    "Concert per invitació" or any value with no number -> None. Member/discount
    tiers (after "(", "/", "socis", "abonats"...) are cut before reading numbers.
    """
    if gratis:
        return "free"
    if not raw:
        return None
    text = raw.strip()
    # Cut off member/discount tiers so we read only the main public price/range.
    main = _PRICE_TIER_CUT.split(text, maxsplit=1)[0]
    nums = [int(m.group(1)) for m in _PRICE_NUM.finditer(main)]
    if not nums:
        # No numeric price: free-admission phrasing -> free, else unknown.
        return "free" if _FREE_MARKERS.search(text) else None
    lo, hi = min(nums), max(nums)
    # format_eur_range applies the 2× rule: a range only when high >= 2× low,
    # otherwise just the highest price.
    return format_eur_range(lo, hi)


def _parse_start(value: str | None) -> tuple[dt.date, dt.time | None] | None:
    """Parse a session start "YYYY-MM-DD HH:MM" (Barcelona wall-clock, kept naive)."""
    if not value or len(value) < 10:
        return None
    try:
        date = dt.date.fromisoformat(value[:10])
    except ValueError:
        return None
    time: dt.time | None = None
    m = re.search(r"(\d{1,2}):(\d{2})", value[10:])
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if h <= 23 and mi <= 59:
            time = dt.time(h, mi)
    return date, time


def _image_url(prod: dict) -> str | None:
    img = prod.get("listing_image")
    if not img:
        return None
    ext = prod.get("listing_image_ext") or ".jpg"
    return f"{BASE_URL}/images/{img}/production_listing{ext}"


def _titles(records: dict, ids, strip_hash: bool = False) -> list[str]:
    """Resolve a list of record ids to their (cleaned) titles, preserving order."""
    out: list[str] = []
    for rid in ids or []:
        rec = records.get(str(rid))
        title = _strip_html(rec.get("title")) if rec else None
        if title:
            out.append(title.lstrip("#") if strip_hash else title)
    return out


def parse_programming(json_text: str) -> list[ScrapedEvent]:
    """Parse the Palau programming JSON into one ScrapedEvent per occurrence.

    Iterates sessions (occurrences), joining each to its production. Skips expired
    or hidden sessions and sessions whose production is missing/hidden. Category is
    `classical` by default, `jazz` when the production carries the #jazz hashtag.
    """
    data = json.loads(json_text)
    productions = data.get("productions", {})
    sessions = data.get("sessions", {})
    hashtags = data.get("hashtags", {})
    cycles = data.get("cycles", {})
    stages = data.get("stages", {})

    events: list[ScrapedEvent] = []
    for sess in sessions.values():
        if sess.get("expired") or sess.get("hidden"):
            continue
        prod = productions.get(str(sess.get("production")))
        if not prod or prod.get("hidden"):
            continue

        parsed = _parse_start((sess.get("start_date") or {}).get("value"))
        if not parsed:
            continue
        start_date, start_time = parsed
        if sess.get("uncertain_start_time"):
            start_time = None

        title = _strip_html(prod.get("title"))
        source_url = prod.get("url")
        if not title or not source_url:
            continue

        hashtag_titles = _titles(hashtags, prod.get("hashtags"), strip_hash=True)
        # The first hashtag that maps to a top-level category wins; remember it so
        # we don't also repeat it as a genre annotation below.
        category = DEFAULT_CATEGORY
        category_hashtag: str | None = None
        for h in hashtag_titles:
            if h.lower() in HASHTAG_CATEGORY:
                category = HASHTAG_CATEGORY[h.lower()]
                category_hashtag = h.lower()
                break

        # Annotations: subtitle + cycle (series) titles + hashtag (genre) labels +
        # the stage when the concert is off-site. Too granular for category_slugs.
        annotations: list[str] = []
        subtitle = _strip_html(prod.get("subtitle"))
        if subtitle:
            annotations.append(subtitle)
        annotations.extend(_titles(cycles, prod.get("cycles")))
        # Genre hashtags as labels, minus the one that already drove the category
        # (e.g. the #jazz hashtag behind category == "jazz", or #flamenc → flamenco).
        annotations.extend(h for h in hashtag_titles if h.lower() != category_hashtag)
        stage_title = _strip_html(
            (stages.get(str(sess.get("stage"))) or {}).get("title")
        )
        if stage_title and stage_title not in _PALAU_STAGES:
            annotations.append(stage_title)

        date_token = start_date.isoformat()
        time_token = start_time.strftime("%H%M") if start_time else "0000"
        external_id = f"{prod.get('id')}@{date_token}T{time_token}"

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                start_times=[start_time] if start_time else [],
                source_url=source_url,
                category_slugs=[category],
                price=_parse_price(prod.get("price"), bool(prod.get("gratis"))),
                image_url=_image_url(prod),
                external_id=external_id,
                annotations=annotations,
            )
        )

    return events


class PalauMusicaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        json_text = httpx.get(
            PROGRAMMING_JSON_URL, follow_redirects=True, timeout=60
        ).text
        return parse_programming(json_text)


register(
    scraper=PalauMusicaScraper(),
    venue=VenueDefinition(
        slug="palau-musica",
        name="Palau de la Música",
        city_slug="barcelona",
        address="C/ Palau de la Música, 4-6, 08003 Barcelona",
        site_url="https://www.palaumusica.cat",
        category_slugs=["classical", "jazz", "flamenco"],
        list_memberships=[
            ListMembership(list_slug="classical", whitelist_category_slug="classical"),
            ListMembership(list_slug="jazz", whitelist_category_slug="jazz"),
            ListMembership(list_slug="flamenco", whitelist_category_slug="flamenco"),
        ],
    ),
)
