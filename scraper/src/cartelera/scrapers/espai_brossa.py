from __future__ import annotations
import datetime as dt
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers.price import format_eur_range
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Espai Brossa / Centre de les Arts Lliures (Fundació Joan Brossa, Barcelona)
# is a low-volume avant-garde performing-arts venue (typically 4-8 events at a
# time). There is NO usable JSON-LD event data — Yoast only emits WebPage
# boilerplate. We scrape the homepage, which lists all current events in
# `article.news-item` cards, then optionally fetch each detail page for price.
#
# Data sources:
#   - List:   https://www.fundaciojoanbrossa.cat/
#   - Detail: e.g. https://fundaciojoanbrossa.cat/arxiu-arts-en-viu/<slug>/
#
# Category mapping (site label → our slug):
#   "Espectacle"  → theater  (live performance / experimental theater)
#   "Exposició"   → theater  (visual poetry / art exhibitions at this venue)
#   "Activitat"   → theater  (default), except "Casal d'estiu" → kids
#
# Events with category "Nota de Premsa" or "General" are press releases / news
# items and are filtered out entirely.

LIST_URL = "https://www.fundaciojoanbrossa.cat/"
VENUE_SLUG = "espai-brossa"

# Site categories that represent calendar events (not press releases / news).
_EVENT_CATEGORIES = {"espectacle", "exposició", "activitat"}

# The site uses DD.MM.YYYY date format in the card headers.
_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")

# Price pattern: "Preu: 17 €" or "Preu: 17€"
_PRICE_RE = re.compile(r"[Pp]reu[:\s]+(\d+(?:[.,]\d+)?)\s*€")
# General euro amount (used as fallback body scan)
_EURO_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*€")
_FREE_RE = re.compile(r"gratu[ïi]t|entrada\s+lliure|entrada\s+gratuïta|entrada libre", re.IGNORECASE)
_SOLDOUT_RE = re.compile(r"sold.?out|entrades\s+exhaurides|esgotades", re.IGNORECASE)


def _parse_date(text: str) -> dt.date | None:
    m = _DATE_RE.search(text)
    if not m:
        return None
    return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def _parse_dates(date_str: str) -> tuple[dt.date, dt.date | None]:
    """Parse a date range like '04.06.2026 - 12.06.2026' or single '11.06.2026'.
    Returns (start_date, end_date_or_None)."""
    matches = _DATE_RE.findall(date_str)
    if not matches:
        raise ValueError(f"No dates found in: {date_str!r}")
    dates = [dt.date(int(y), int(mo), int(d)) for d, mo, y in matches]
    start = dates[0]
    end = dates[-1] if len(dates) > 1 and dates[-1] != start else None
    return start, end


def _slug_from_url(url: str) -> str:
    """Extract the final path segment as a stable slug."""
    return url.rstrip("/").split("/")[-1]


def _parse_price_from_info(info_text: str) -> str | None:
    """Extract a price string from a detail page's INFO ÚTIL text block.

    Looks for explicit 'Preu: N €' patterns, free-entry phrases, and sold-out
    markers. Returns None when no price is found — suitable for passing the
    same text to the broader body-scan fallback.
    """
    if _SOLDOUT_RE.search(info_text):
        return "sold-out"
    if _FREE_RE.search(info_text):
        return "free"
    m = _PRICE_RE.search(info_text)
    if m:
        raw = m.group(1).replace(",", ".")
        try:
            euros = int(float(raw))
            return f"{euros}€"
        except ValueError:
            return f"{raw}€"
    return None


def _parse_price_from_body(body_text: str) -> str | None:
    """Broad body-text price scan for pages that embed prices in main content
    rather than a sidebar (e.g. Activitats with registration forms).

    Collects all euro amounts in the body, then returns a formatted range/price
    via format_eur_range(). Ignores solitary very-large values that likely come
    from navigation/footer noise (> 500€).
    """
    if _SOLDOUT_RE.search(body_text):
        return "sold-out"
    if _FREE_RE.search(body_text):
        return "free"
    amounts = []
    for m in _EURO_RE.finditer(body_text):
        raw = m.group(1).replace(",", ".")
        try:
            val = int(float(raw))
            if 0 < val <= 500:
                amounts.append(val)
        except ValueError:
            pass
    if not amounts:
        return None
    lo, hi = min(amounts), max(amounts)
    return format_eur_range(lo, hi)


def _fetch_detail_price(url: str, client: httpx.Client) -> str | None:
    """Fetch an event detail page and extract the price.

    First checks the `.sidebar-expos` INFO ÚTIL block. If no price is found
    there, falls back to scanning the full page body (needed for Activitats
    pages like 'Casal d'estiu' which embed pricing in the main content body).
    """
    try:
        resp = client.get(url, follow_redirects=True, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        # Primary: first sidebar block (INFO ÚTIL) — explicit "Preu: N€" format
        sidebars = soup.select(".sidebar-expos")
        if sidebars:
            price = _parse_price_from_info(sidebars[0].get_text(" ", strip=True))
            if price is not None:
                return price
        # Fallback: broad body scan — for Activitat pages that embed pricing
        # in the main content rather than a sidebar (e.g. Casal d'estiu).
        # Restrict to the main content section to avoid footer noise.
        main = soup.select_one(".entry-content, .post-content, #content, main")
        body_text = main.get_text(" ", strip=True) if main else soup.get_text(" ", strip=True)
        return _parse_price_from_body(body_text)
    except Exception:
        return None


def _map_category(site_cat: str, title: str) -> str:
    """Map a site-level category label to our known category slugs."""
    cat = site_cat.strip().lower()
    title_lower = title.lower()
    if "activitat" in cat:
        # Summer camp / children's workshop
        if "casal" in title_lower or "escola" in title_lower or "infants" in title_lower:
            return "kids"
        return "theater"
    # espectacle and exposició both map to theater at this performing-arts venue
    return "theater"


def parse_agenda(html: str) -> list[ScrapedEvent]:
    """Parse the Espai Brossa homepage into ScrapedEvents.

    Each `article.news-item` card carries title, date range, category label,
    detail URL and thumbnail. Price is NOT available on the list page — this
    function leaves price=None for all events. The live scraper fetches detail
    pages to fill price. This function is kept pure (no network) for offline
    tests.
    """
    soup = BeautifulSoup(html, "html.parser")
    events: list[ScrapedEvent] = []
    seen: set[str] = set()

    for article in soup.select("article.news-item"):
        # Category label from the date/category row
        flex_divs = article.select(".flex.justify-between div")
        if len(flex_divs) < 2:
            continue
        date_str = flex_divs[0].get_text(strip=True)
        site_cat = flex_divs[-1].get_text(strip=True)

        # Skip news items / press releases
        if site_cat.strip().lower() not in _EVENT_CATEGORIES:
            continue

        # Title: prefer the first h3 (two identical h3 exist for hover effect)
        h3 = article.select_one("h3 span")
        if not h3:
            continue
        title = h3.get_text(strip=True)
        if not title:
            continue

        # Detail URL
        link = article.select_one("a")
        if not link or not link.get("href"):
            continue
        source_url = str(link["href"]).rstrip("/")
        if not source_url.startswith("http"):
            source_url = "https://www.fundaciojoanbrossa.cat" + source_url
        if source_url in seen:
            continue
        seen.add(source_url)

        # Dates
        try:
            start_date, end_date = _parse_dates(date_str)
        except ValueError:
            continue

        # Category
        category = _map_category(site_cat, title)

        # Subtitle / author (h4)
        h4 = article.select_one("h4")
        subtitle = h4.get_text(strip=True) if h4 else None

        # Description snippet
        desc_div = article.select_one(".mt-2.text-sm div")
        description = desc_div.get_text(" ", strip=True) if desc_div else None

        # Thumbnail
        img = article.select_one("img")
        image_url = img.get("src") if img else None
        # Prefer a larger srcset image
        if img and img.get("srcset"):
            srcset_parts = img["srcset"].split(",")
            # Take the first (original/largest) entry
            first = srcset_parts[0].strip().split(" ")[0]
            if first.startswith("http"):
                image_url = first

        # external_id: URL slug — each show has a unique slug, single row per run
        ext_id = _slug_from_url(source_url)

        annotations: list[str] = []
        if subtitle:
            annotations.append(subtitle)
        if site_cat and site_cat.lower() != category:
            annotations.append(site_cat)

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                end_date=end_date,
                source_url=source_url,
                category_slugs=[category],
                price=None,  # filled in by live scraper via detail page
                description=description,
                image_url=image_url,
                external_id=ext_id,
                annotations=annotations,
            )
        )

    return events


class EspaiBrossaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with httpx.Client(timeout=30) as client:
            resp = client.get(LIST_URL, follow_redirects=True)
            events = parse_agenda(resp.text)
            # Enrich each event with a price from its detail page
            for ev in events:
                ev.price = _fetch_detail_price(ev.source_url, client)
        return events


register(
    scraper=EspaiBrossaScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Espai Brossa / Centre de les Arts Lliures",
        city_slug="barcelona",
        address="C/ Flassaders, 40, 08003 Barcelona",
        site_url="https://www.fundaciojoanbrossa.cat",
        category_slugs=["theater", "kids"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
