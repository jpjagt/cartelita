"""Graner (La Marina, Barcelona) — dance / live-arts creation centre.

Graner promotes and supports creation processes and research around body,
movement and choreographic language. It is NOT a ticketed venue with a dense
programme: public dated activities are sparse (a handful per month — public
presentations, workshops, neighbourhood activations). Everything maps to `dance`.

Data source: the events agenda is rendered server-side in the HOMEPAGE HTML, in
`.home-agenda__container` (one current-month "schedule" block). The standalone
agenda/archive template is a decoy — it renders only a placeholder card ("titol",
"2/2/2023"). The WP REST API exposes only post/page (the custom post types aren't
REST-enabled), and detail pages carry no structured date/time/price. So the
homepage agenda block is the canonical structured source.

Per card (`.home-agenda__element`):
  day   -> .home-agenda__date-day        title -> h5
  month -> .home-agenda__date-month       url  -> a.home-agenda__link[href]
  (3-letter uppercase abbrev, e.g. JUN)   img  -> img[src]
Time/price are not on the site -> None.

Canonical content is Catalan (https://granerbcn.cat/); the English homepage
(https://granerbcn.cat/en/) supplies a ca->en translation, matched by (day,month).

external_id: graner-<YYYY-MM-DD>-<url-slug>  (per occurrence).

Verified: 2026-06-09
"""
from __future__ import annotations

import datetime as dt
import re
import urllib.parse

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.types import ListMembership, ScrapedEvent, ScrapedTranslation, VenueDefinition

CA_URL = "https://granerbcn.cat/"
EN_URL = "https://granerbcn.cat/en/"
VENUE_SLUG = "graner"

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# 3-letter month abbreviation (uppercase) -> month number. The site uses the same
# Catalan/Spanish abbreviations across all WPML languages.
_MONTH_ABBR: dict[str, int] = {
    "GEN": 1, "ENE": 1,
    "FEB": 2,
    "MAR": 3,
    "ABR": 4,
    "MAI": 5, "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SET": 9, "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DES": 12, "DIC": 12,
}


def _guess_year(month: int, today: dt.date | None = None) -> int:
    """Infer the year for a bare month: this year, or next year if month < now."""
    today = today or dt.date.today()
    if month < today.month:
        return today.year + 1
    return today.year


def _slug_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] if path else ""


def _parse_card(el) -> dict | None:
    """Parse one .home-agenda__element into a dict, or None if unusable."""
    day_el = el.select_one(".home-agenda__date-day")
    month_el = el.select_one(".home-agenda__date-month")
    title_el = el.select_one("h5")
    link_el = el.select_one("a")
    if not (day_el and month_el and title_el and link_el):
        return None

    day_txt = day_el.get_text(strip=True)
    month_txt = month_el.get_text(strip=True).upper()
    if not re.fullmatch(r"\d{1,2}", day_txt):
        return None
    month = _MONTH_ABBR.get(month_txt[:3])
    if not month:
        return None
    day = int(day_txt)

    title = title_el.get_text(" ", strip=True)
    href = (link_el.get("href") or "").strip()
    if not title or not href:
        return None

    img_el = el.select_one("img")
    image_url = img_el.get("src") if img_el else None

    return {
        "day": day,
        "month": month,
        "title": title,
        "source_url": href,
        "image_url": image_url,
    }


def _parse_home(html: str) -> list[dict]:
    """Parse the homepage agenda cards into raw dicts (no ScrapedEvent yet)."""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".home-agenda__container")
    if not container:
        return []
    cards: list[dict] = []
    for el in container.select(".home-agenda__element"):
        card = _parse_card(el)
        if card:
            cards.append(card)
    return cards


def parse_agenda(
    ca_html: str,
    en_html: str | None = None,
    today: dt.date | None = None,
) -> list[ScrapedEvent]:
    """Pure parser: Catalan (canonical) + optional English homepage -> events.

    English cards are matched to Catalan cards by their (day, month) slot to add
    a ca->en title/url translation.
    """
    ca_cards = _parse_home(ca_html)
    en_by_slot: dict[tuple[int, int], dict] = {}
    if en_html:
        for c in _parse_home(en_html):
            en_by_slot.setdefault((c["day"], c["month"]), c)

    events: list[ScrapedEvent] = []
    seen_ids: set[str] = set()
    for c in ca_cards:
        year = _guess_year(c["month"], today=today)
        try:
            start_date = dt.date(year, c["month"], c["day"])
        except ValueError:
            continue

        slug = _slug_from_url(c["source_url"]) or "event"
        external_id = f"graner-{start_date.isoformat()}-{slug}"
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)

        translations: list[ScrapedTranslation] = []
        en = en_by_slot.get((c["day"], c["month"]))
        if en and en["title"] != c["title"]:
            translations.append(
                ScrapedTranslation(
                    lang="en",
                    title=en["title"],
                    source_url=en["source_url"],
                )
            )

        events.append(
            ScrapedEvent(
                title=c["title"],
                start_date=start_date,
                start_time=None,  # not on the site
                source_url=c["source_url"],
                category_slugs=["dance"],
                price=None,  # not on the site
                image_url=c["image_url"],
                external_id=external_id,
                translations=translations,
            )
        )
    return events


class GranerScraper:
    venue_slug = VENUE_SLUG

    def _get(self, url: str) -> str:
        r = httpx.get(url, headers=_HEADERS, follow_redirects=True, timeout=30)
        r.raise_for_status()
        return r.text

    def scrape(self) -> list[ScrapedEvent]:
        ca_html = self._get(CA_URL)
        try:
            en_html = self._get(EN_URL)
        except Exception:
            en_html = None
        return parse_agenda(ca_html, en_html)


register(
    scraper=GranerScraper(),
    venue=VenueDefinition(
        slug="graner",
        name="Graner",
        city_slug="barcelona",
        address="C/ Bot, 5, Marina (Port)",
        site_url="https://granerbcn.cat/",
        category_slugs=["dance"],
        list_memberships=[ListMembership(list_slug="dance", whitelist_category_slug="dance")],
    ),
)
