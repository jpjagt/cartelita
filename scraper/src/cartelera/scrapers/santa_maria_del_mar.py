from __future__ import annotations
import datetime as dt
import html as html_module
import re
import time

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Basílica de Santa Maria del Mar (El Born, Barcelona) — a Gothic basilica whose
# cultural programme is organ recitals (the "L'Orgue del Mar" cycle) and choral /
# classical concerts. The old `santamariadelmarbarcelona.org` domain is now a
# meta-refresh redirect to `santamariadelmar.barcelona`; there is no dedicated
# concerts page, only a single WordPress *Agenda* that mixes concerts with parish
# events (retreats, masses). We read the agenda list (one `article` per post:
# title, detail URL, event date, image), keep the concerts via a title filter, and
# fetch each kept concert's detail page for time + price (the list carries neither).
# See santa_maria_del_mar_SOURCE.md.
BASE_URL = "https://www.santamariadelmar.barcelona"
AGENDA_URL = f"{BASE_URL}/ca/agenda/"
VENUE_SLUG = "santa-maria-del-mar"

# Bound the pagination walk — the agenda is a small archive.
_MAX_PAGES = 8

_DDMMYYYY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_TIME = re.compile(r"(\d{1,2})[:.h](\d{2})?")
# A price like "9€" / "9 €" / "9,50€".
_PRICE = re.compile(r"(\d+(?:[.,]\d+)?)\s*€")

# Title keywords that mark a cultural concert (vs. parish events we drop).
_CONCERT_KEYWORDS = (
    "concert",
    "cant de la sibil",  # medieval choral piece
    "coral",
    "gòspel",
    "gospel",
    "rèquiem",
    "requiem",
    "escolania",
    "capella de música",
)
# Catalan/Spanish free-entry phrases to normalize to "free".
_FREE_PHRASES = (
    "entrada gratuïta",
    "entrada gratuita",
    "activitat gratuïta",
    "entrada lliure",
    "entrada libre",
    "concert gratuït",
    "gratis",
)


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").strip()


def _absolutize(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE_URL + url
    return url


def _is_concert(title: str) -> bool:
    low = title.lower()
    return any(k in low for k in _CONCERT_KEYWORDS)


def _parse_date(text: str) -> dt.date | None:
    m = _DDMMYYYY.search(text or "")
    if not m:
        return None
    d, mo, y = (int(g) for g in m.groups())
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


def _cycle_annotation(title: str) -> str | None:
    """Pull the programming cycle out of a title like `… – Cicle «X» de 2026`."""
    m = re.search(r"cicle\s+[«\"']?([^»\"']+)", title, re.I)
    if m:
        return "Cicle " + _clean(m.group(1)).strip(" «»\"'")
    return None


def parse_agenda(html: str) -> list[ScrapedEvent]:
    """Parse one agenda list page into ScrapedEvents (concerts only).

    One ScrapedEvent per concert `article`: title from `h3.grve-post-title`, detail
    URL from `a.grve-item-url`, event date from `.grve-post-date` (`dd/mm/yyyy` —
    verified to equal the detail page's `Data:`), image from the structured-data
    block. Non-concert parish posts (retreats, masses) are filtered out by title.
    Time and price are NOT on the list — `SantaMariaDelMarScraper.scrape()` enriches
    each kept event from its detail page. This pure function is the offline-testable
    core; it sets `price=None` (filled in later)."""
    soup = BeautifulSoup(html, "html.parser")

    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for art in soup.select("article"):
        title_el = art.select_one("h3.grve-post-title")
        link_el = art.select_one("a.grve-item-url")
        if not title_el or not link_el:
            continue
        title = _clean(title_el.get_text(" ", strip=True))
        href = (link_el.get("href") or "").strip()
        if not title or not href or not _is_concert(title):
            continue

        date_el = art.select_one(".grve-post-date")
        start_date = _parse_date(date_el.get_text(" ", strip=True) if date_el else "")
        if start_date is None:
            continue  # no reliable date; skip rather than guess

        source_url = _absolutize(href.split("?")[0])
        slug = source_url.rstrip("/").rsplit("/", 1)[-1]
        external_id = f"{slug}@{start_date.isoformat()}"
        if external_id in seen:
            continue
        seen.add(external_id)

        img_el = art.select_one("span[itemprop=image] span[itemprop=url]")
        image_url = _clean(img_el.get_text(strip=True)) if img_el else None

        annotations: list[str] = []
        cycle = _cycle_annotation(title)
        if cycle:
            annotations.append(cycle)

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                source_url=source_url,
                category_slugs=["classical"],
                image_url=image_url,
                price=None,  # filled from the detail page
                external_id=external_id,
                annotations=annotations,
            )
        )

    return events


def parse_detail(html: str) -> tuple[dt.time | None, str | None]:
    """Extract (time, price) from a concert detail page.

    Scoped to `.elementor-widget-theme-post-content` (the post body) to avoid the
    nav/sidebar. Reads `Hora:` for the local showtime and `Entrada:`/`Preu:` for the
    main public price (discount/reduced tiers are skipped per the price convention)."""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".elementor-widget-theme-post-content") or soup
    text = content.get_text("\n", strip=True)

    start_time = None
    price = None
    for raw in text.split("\n"):
        line = _clean(raw)
        low = line.lower()
        if start_time is None and low.startswith("hora"):
            m = _TIME.search(line)
            if m:
                hh = int(m.group(1))
                mm = int(m.group(2)) if m.group(2) else 0
                if 0 <= hh < 24 and 0 <= mm < 60:
                    start_time = dt.time(hh, mm)
        if price is None and (low.startswith("entrada") or low.startswith("preu")):
            # Skip the reduced/discount tier; keep the main public price.
            if "reduïda" in low or "reduida" in low or "reduc" in low:
                continue
            if any(p in low for p in _FREE_PHRASES):
                price = "free"
            else:
                m = _PRICE.search(line)
                if m:
                    price = f"{m.group(1)}€"
        # A free-entry phrase anywhere in the body (no explicit Entrada line).
        if price is None and any(p in low for p in _FREE_PHRASES):
            price = "free"

    return start_time, price


class SantaMariaDelMarScraper:
    venue_slug = VENUE_SLUG

    def _get(self, client: httpx.Client, url: str) -> str | None:
        for attempt in range(3):
            try:
                resp = client.get(url)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPError:
                if attempt == 2:
                    return None
                time.sleep(2)
        return None

    def scrape(self) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        seen: set[str] = set()
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            for page in range(1, _MAX_PAGES + 1):
                url = AGENDA_URL if page == 1 else f"{AGENDA_URL}page/{page}/"
                html = self._get(client, url)
                if not html:
                    break
                page_events = parse_agenda(html)
                if not page_events and page > 1:
                    break
                new = [e for e in page_events if e.external_id not in seen]
                if not new and page > 1:
                    break
                for ev in new:
                    seen.add(ev.external_id)
                events.extend(new)

            # Enrich each concert with time + price from its detail page.
            for ev in events:
                detail_html = self._get(client, ev.source_url)
                if not detail_html:
                    continue
                start_time, price = parse_detail(detail_html)
                if start_time is not None:
                    ev.start_time = start_time
                if price is not None:
                    ev.price = price

        return events


register(
    scraper=SantaMariaDelMarScraper(),
    venue=VenueDefinition(
        slug="santa-maria-del-mar",
        name="Basílica de Santa Maria del Mar",
        city_slug="barcelona",
        address="Plaça de Santa Maria, 1, Ciutat Vella, 08003 Barcelona",
        site_url="https://www.santamariadelmar.barcelona",
        category_slugs=["classical"],
        list_memberships=[
            ListMembership(list_slug="classical"),
        ],
    ),
)
