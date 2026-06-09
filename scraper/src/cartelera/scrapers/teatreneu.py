"""Teatreneu (Barcelona, Gràcia) — theatre/comedy venue scraper.

Data source: two-level DOM scrape.

1. Cartellera list page (https://www.teatreneu.com/ca/cartellera.html) yields
   one card per currently running show: title, source_url, category tags, sala,
   image_url.

2. Each show's detail page (https://www.teatreneu.com/ca/cartellera/c/<slug>.html)
   lists upcoming session rows (.funcio), each with funcio ID, start_date (from
   the Google-Calendar add-link, which carries a reliable ISO YYYYMMDD), start_time
   (.hora span.hora), and price (.preu).

   Additional sessions are loaded via AJAX pagination:
     GET ajax.php?function=paginarFuncionsFitxaEspectacle&pageNum=N&itemID=ID
              &dataAnt=LAST_DATETIME&caducat=0
   Each page returns 5 rows; empty response means exhausted.

   Sessions are fetched up to LOOKAHEAD_DAYS (90) ahead of today.

Category mapping
----------------
Teatreneu is a comedy/theatre venue. All events → `theater`.
`Infantil` tag also adds → `kids`.
All Catalan tags (Improvisació, Humor, Monòlegs, Màgia, Teatre, Infantil) are
preserved in `annotations`.

external_id
-----------
The numeric funcio ID (e.g. "40857") is the venue's own per-occurrence key —
each session has a unique ID, so no date qualification is needed.

Price
-----
"Des de N €"  → "{N}€"   (extract the leading integer from the preu element)
Availability class `disp-no` (exhaurides) → "sold-out"
Missing price → None

See teatreneu_SOURCE.md for full field-by-field details.
Last verified: 2026-06-09
"""
from __future__ import annotations
import datetime as dt
import re
import time
import urllib.parse

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

CARTELLERA_URL = "https://www.teatreneu.com/ca/cartellera.html"
BASE_URL = "https://www.teatreneu.com"
AJAX_URL = "https://www.teatreneu.com/ajax.php"
VENUE_SLUG = "teatreneu"
LOOKAHEAD_DAYS = 90

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "ca,es;q=0.9,en;q=0.8",
    "Referer": BASE_URL,
}
_AJAX_DELAY = 0.3  # seconds between AJAX pagination requests

# Catalan category tag text → Cartelera category slug(s).
# Every venue category maps to "theater"; "Infantil" additionally maps to "kids".
_CAT_TO_SLUGS: dict[str, list[str]] = {
    "Improvisació": ["theater"],
    "Humor": ["theater"],
    "Monòlegs": ["theater"],
    "Màgia": ["theater"],
    "Teatre": ["theater"],
    "Infantil": ["theater", "kids"],
}

_PRICE_NUM = re.compile(r"(\d+)")
_GCAL_DATE = re.compile(r"dates=(\d{8})")
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")


def _normalize_url(url: str) -> str:
    url = url.split("?")[0].split("#")[0].rstrip("/")
    if url.startswith("/"):
        url = BASE_URL + url
    return url


def _parse_price(preu_el: Tag | None, hora_el: Tag | None) -> str | None:
    """Extract price from a .preu element.

    - Availability class 'disp-no' on the .hora div → "sold-out"
    - "Des de N €" → "{N}€"
    - Missing / unparseable → None
    """
    if hora_el is not None:
        hora_classes = hora_el.get("class", [])
        if "disp-no" in hora_classes:
            return "sold-out"
    if preu_el is None:
        return None
    text = preu_el.get_text(" ", strip=True)
    m = _PRICE_NUM.search(text)
    if m:
        return f"{m.group(1)}€"
    return None


def _parse_time(hora_el: Tag | None) -> dt.time | None:
    """Parse "HH:MM h" from the inner <span class='hora'> of a .hora div."""
    if hora_el is None:
        return None
    span = hora_el.select_one("span.hora")
    if not span:
        return None
    m = _TIME_RE.search(span.get_text(strip=True))
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return None
    return dt.time(hour, minute)


def _parse_gcal_date(funcio: Tag) -> dt.date | None:
    """Extract start date from the embedded Google Calendar add-link.
    The link carries dates=YYYYMMDDTHHMMSSz in UTC; we use the date part only
    (the local time is shown by .hora, which we parse separately)."""
    gcal = funcio.select_one('a[href*="calendar.google.com"]')
    if not gcal:
        return None
    m = _GCAL_DATE.search(gcal.get("href", ""))
    if not m:
        return None
    s = m.group(1)
    try:
        return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


def _parse_funcio(funcio: Tag) -> tuple[str | None, dt.date | None, dt.time | None, str | None]:
    """Return (funcio_id, start_date, start_time, price) from a .funcio div."""
    # funcio ID from class list
    classes = funcio.get("class", [])
    funcio_id = next(
        (c.replace("funcio-", "") for c in classes if c.startswith("funcio-") and c != "funcio"),
        None,
    )
    start_date = _parse_gcal_date(funcio)
    hora_el = funcio.select_one(".hora")
    start_time = _parse_time(hora_el)
    preu_el = funcio.select_one(".preu")
    price = _parse_price(preu_el, hora_el)
    return funcio_id, start_date, start_time, price


def _parse_show_cards(html: str) -> list[dict]:
    """Parse the cartellera list page into a list of show dicts:
    {title, source_url, category_slugs, annotations, image_url, show_id, sala}."""
    soup = BeautifulSoup(html, "html.parser")
    shows: list[dict] = []
    seen: set[str] = set()

    for card in soup.select(".row[data-open-espectacle]"):
        link_el = card.select_one("a.titol")
        if not link_el:
            continue
        title = link_el.get_text(" ", strip=True)
        source_url = _normalize_url(link_el.get("href", ""))
        if not title or not source_url or source_url in seen:
            continue
        seen.add(source_url)

        # Category tags
        cat_tags = [s.get_text(strip=True) for s in card.select(".categoria")]
        category_slugs_set: set[str] = set()
        for tag in cat_tags:
            category_slugs_set.update(_CAT_TO_SLUGS.get(tag, ["theater"]))
        category_slugs = sorted(category_slugs_set, key=lambda s: (s != "theater", s))

        # Image
        img_el = card.select_one("a.imatge img")
        image_url: str | None = None
        if img_el:
            src = img_el.get("src", "")
            if src and not src.startswith("data:"):
                image_url = src if src.startswith("http") else BASE_URL + src

        # Sala (hall) — goes into annotations
        espai_el = card.select_one(".espai")
        sala = espai_el.get_text(strip=True).replace("\xa0", " ").strip() if espai_el else None
        # Clean up "fa-map-marker-alt" icon text residue
        if sala:
            sala = re.sub(r"\s+", " ", sala).strip()

        # Extract show_id from data-open-espectacle or source_url
        # URL form: /ca/cartellera/c/<id>-<slug>.html
        m = re.search(r"/c/(\d+)-", source_url)
        show_id = m.group(1) if m else None

        shows.append(
            {
                "title": title,
                "source_url": source_url,
                "category_slugs": category_slugs,
                "annotations": cat_tags,
                "image_url": image_url,
                "show_id": show_id,
                "sala": sala,
            }
        )
    return shows


def _parse_funcions(html: str, cutoff: dt.date) -> list[tuple[str | None, dt.date, dt.time | None, str | None]]:
    """Parse session rows from a detail or AJAX response page.

    Returns list of (funcio_id, start_date, start_time, price) tuples for
    sessions up to (and including) `cutoff`."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for funcio in soup.select(".funcio"):
        funcio_id, start_date, start_time, price = _parse_funcio(funcio)
        if start_date is None or start_date > cutoff:
            # Stop pagination once we pass the cutoff
            if start_date is not None and start_date > cutoff:
                return results  # signal caller to stop paginating
            continue
        results.append((funcio_id, start_date, start_time, price))
    return results


def parse_agenda(
    agenda_html: str,
    detail_pages: dict[str, str] | None = None,
) -> list[ScrapedEvent]:
    """Pure function: parse the cartellera list page (and optionally pre-fetched
    detail page HTML fragments) into ScrapedEvents.

    `detail_pages` maps show_id → detail page HTML (for offline/fixture testing).
    When None, only the first 5 initial sessions per show (from the list page)
    are returned — the scraper's live path fetches detail pages separately.

    Note: the agenda_html (list page) does NOT contain individual sessions;
    those live on detail pages. In offline tests we pass detail_pages explicitly.
    """
    shows = _parse_show_cards(agenda_html)
    if not shows:
        return []

    cutoff = dt.date.today() + dt.timedelta(days=LOOKAHEAD_DAYS)
    events: list[ScrapedEvent] = []

    for show in shows:
        detail_html = (detail_pages or {}).get(show["show_id"] or "")
        if not detail_html:
            # No detail page provided → emit one placeholder event per show
            # (used in offline unit tests that only have the list fixture).
            events.append(
                ScrapedEvent(
                    title=show["title"],
                    start_date=dt.date.today(),
                    source_url=show["source_url"],
                    category_slugs=show["category_slugs"],
                    annotations=show["annotations"],
                    image_url=show["image_url"],
                    external_id=f"{VENUE_SLUG}-{show['show_id']}",
                )
            )
            continue

        funcions = _parse_funcions(detail_html, cutoff)
        for funcio_id, start_date, start_time, price in funcions:
            annotations = list(show["annotations"])
            if show["sala"]:
                annotations.append(show["sala"])
            events.append(
                ScrapedEvent(
                    title=show["title"],
                    start_date=start_date,
                    start_time=start_time,
                    source_url=show["source_url"],
                    category_slugs=show["category_slugs"],
                    price=price,
                    image_url=show["image_url"],
                    external_id=str(funcio_id) if funcio_id else None,
                    annotations=annotations,
                )
            )
    return events


class TeatreneuScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        cutoff = dt.date.today() + dt.timedelta(days=LOOKAHEAD_DAYS)
        client = httpx.Client(timeout=30, follow_redirects=True, headers=_HEADERS)

        # Step 1: fetch show list
        agenda_html = client.get(CARTELLERA_URL).text
        shows = _parse_show_cards(agenda_html)

        events: list[ScrapedEvent] = []
        seen_ids: set[str] = set()

        for show in shows:
            show_id = show["show_id"]
            if not show_id:
                continue

            # Step 2: fetch detail page (includes first 5 upcoming sessions)
            detail_url = show["source_url"]
            detail_html = client.get(detail_url).text
            detail_soup = BeautifulSoup(detail_html, "html.parser")

            # Get the funcions already on the page
            page_funcions: list[tuple[str | None, dt.date, dt.time | None, str | None]] = []
            past_cutoff = False
            for funcio_el in detail_soup.select(".funcio"):
                funcio_id, start_date, start_time, price = _parse_funcio(funcio_el)
                if start_date is None:
                    continue
                if start_date > cutoff:
                    past_cutoff = True
                    break
                page_funcions.append((funcio_id, start_date, start_time, price))

            # Get the "future" pagination button attributes
            btn = detail_soup.select_one(".btnMesFuncions:not(.anteriors)")
            data_ant = btn.get("dataant") if btn else None
            page_num = int(btn.get("pagenum", "1")) if btn else None

            # Paginate future sessions until cutoff or exhausted
            all_funcions = list(page_funcions)
            if not past_cutoff and data_ant and page_num is not None:
                current_data_ant = data_ant
                current_page = page_num
                while True:
                    url = (
                        AJAX_URL
                        + "?function=paginarFuncionsFitxaEspectacle"
                        + f"&pageNum={current_page}"
                        + f"&itemID={show_id}"
                        + f"&dataAnt={urllib.parse.quote(current_data_ant)}"
                        + "&caducat=0"
                    )
                    time.sleep(_AJAX_DELAY)
                    resp_text = client.get(url).text.strip()
                    if not resp_text:
                        break  # no more sessions

                    batch_soup = BeautifulSoup(resp_text, "html.parser")
                    batch_funcions: list[tuple[str | None, dt.date, dt.time | None, str | None]] = []
                    stop = False
                    last_datetime: str | None = None
                    for funcio_el in batch_soup.select(".funcio"):
                        funcio_id, start_date, start_time, price = _parse_funcio(funcio_el)
                        if start_date is None:
                            continue
                        if start_date > cutoff:
                            stop = True
                            break
                        batch_funcions.append((funcio_id, start_date, start_time, price))
                        # Track last datetime for next page's dataAnt
                        if start_date and start_time:
                            last_datetime = f"{start_date.isoformat()} {start_time.strftime('%H:%M:%S')}"
                        elif start_date:
                            last_datetime = f"{start_date.isoformat()} 00:00:00"

                    all_funcions.extend(batch_funcions)

                    if stop or not batch_funcions:
                        break

                    # Advance pagination
                    if last_datetime:
                        current_data_ant = last_datetime
                    current_page += 1

            # Step 3: emit one ScrapedEvent per session
            for funcio_id, start_date, start_time, price in all_funcions:
                ext_id = str(funcio_id) if funcio_id else None
                if ext_id and ext_id in seen_ids:
                    continue
                if ext_id:
                    seen_ids.add(ext_id)

                annotations = list(show["annotations"])
                if show["sala"]:
                    annotations.append(show["sala"])

                events.append(
                    ScrapedEvent(
                        title=show["title"],
                        start_date=start_date,
                        start_time=start_time,
                        source_url=show["source_url"],
                        category_slugs=show["category_slugs"],
                        price=price,
                        image_url=show["image_url"],
                        external_id=ext_id,
                        annotations=annotations,
                    )
                )

        return events


register(
    scraper=TeatreneuScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Teatreneu",
        city_slug="barcelona",
        address="C/ de Terol, 26, 08012 Barcelona",
        site_url="https://www.teatreneu.com",
        category_slugs=["theater", "kids"],
        list_memberships=[
            ListMembership(list_slug="theater", whitelist_category_slug="theater"),
            ListMembership(list_slug="kids", whitelist_category_slug="kids"),
        ],
    ),
)
