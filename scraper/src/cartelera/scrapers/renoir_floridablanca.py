from __future__ import annotations
import datetime as dt
import html as html_module
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Renoir Floridablanca (Cines Renoir, Barcelona) server-renders a daily cartelera:
# one film block per movie, each block listing every showtime ("pase") for that
# day as a buy link to pillalas.com. The block carries title, detail link, poster,
# director, version (VOSE/VOSC) and age rating; the per-session pillalas `pase` id
# is a unique per-occurrence key. A single request per day is a complete source —
# we iterate the day picker (today + ~6 days). See renoir_floridablanca_SOURCE.md.
#
# Each film block is rendered three times (responsive variants); we read only the
# desktop `.d-none.d-lg-block` copy to avoid triplicating every event.
BASE_URL = "https://www.cinesrenoir.com"
CARTELERA_URL = f"{BASE_URL}/cine/renoir-floridablanca/cartelera/"
VENUE_SLUG = "renoir-floridablanca"

# The cartelera carries no per-screening price. Renoir's price table is heavily
# tiered (weekday vs weekend vs "día del espectador" vs promos), but the spread is
# minor (8,50€→9,80€, high < 2× low) and the page gives no per-session signal of
# which tier applies — so per the price convention we don't show a range; we apply
# the highest general-admission (weekend) adult ticket to every event.
DEFAULT_PRICE = "9,80€"

# How many days (incl. today) to scrape if the day picker can't be read.
_FALLBACK_DAYS = 7

_FECHA = re.compile(r"fecha=(\d{4})-(\d{2})-(\d{2})")
_HOUR = re.compile(r"(\d{1,2}):(\d{2})")
_PASE_ID = re.compile(r"/pase/(\d+)")


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").strip()


def _absolutize(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE_URL + url
    return url


def _page_date(soup: BeautifulSoup) -> dt.date | None:
    """The day this cartelera page renders, from the selected day-picker option.

    `<select id="elige-dia">` lists the available days; the option marked
    "(seleccionado)"/"(selected)" carries `?fecha=YYYY-MM-DD`. This makes the
    parse deterministic for a saved fixture and correct per-page in production."""
    sel = soup.find("select", id="elige-dia")
    if not sel:
        return None
    selected = None
    for opt in sel.find_all("option"):
        text = opt.get_text(strip=True).lower()
        if "seleccion" in text or "selected" in text:
            selected = opt
            break
    if selected is None:
        return None
    m = _FECHA.search(selected.get("value", ""))
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _available_dates(soup: BeautifulSoup) -> list[dt.date]:
    """All day-picker dates (today + the next several days)."""
    sel = soup.find("select", id="elige-dia")
    dates: list[dt.date] = []
    if sel:
        for opt in sel.find_all("option"):
            m = _FECHA.search(opt.get("value", ""))
            if not m:
                continue
            try:
                d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
            if d not in dates:
                dates.append(d)
    return dates


def _block_title_and_url(block: Tag) -> tuple[str | None, str | None]:
    link = block.select_one('.col-4 a[href^="/pelicula/"]')
    if not link:
        return None, None
    title = _clean(link.get_text(strip=True))
    href = link.get("href", "").split("?")[0]
    return (title or None), (_absolutize(href) if href else None)


def _block_image(block: Tag) -> str | None:
    img = block.select_one(".col-1 img[src]")
    src = img.get("src", "") if img else ""
    return _absolutize(src) if src else None


def _block_meta(block: Tag) -> tuple[str | None, list[str]]:
    """Director (-> description) and version/age-rating smalls (-> annotations)."""
    director: str | None = None
    annotations: list[str] = []
    for small in block.select(".col-4 small"):
        text = _clean(small.get_text(" ", strip=True))
        if not text:
            continue
        b = small.find("b")
        if b and director is None and not annotations:
            # First bold small is the director line ("de <Name>").
            director = _clean(b.get_text(" ", strip=True))
            continue
        if "versión" in text.lower() or "v.o" in text.lower():
            annotations.append(text)
        elif "recomendada" in text.lower() or "apta" in text.lower():
            annotations.append(text)
    description = director or None
    return description, annotations


def _session_time(pase: Tag) -> tuple[dt.time | None, str | None]:
    """(showtime, pase-id) from a `.pase-cartelera`. The buy link is matched by its
    pillalas `/pase/` href (not button class: special events use `btn-evento`)."""
    link = pase.select_one('a[href*="pillalas.com/pase"]')
    if not link:
        return None, None
    pid_m = _PASE_ID.search(link.get("href", ""))
    pase_id = pid_m.group(1) if pid_m else None
    hm = _HOUR.search(link.get_text(strip=True))
    if not hm:
        return None, pase_id
    hh, mm = int(hm.group(1)), int(hm.group(2))
    t = dt.time(hh, mm) if 0 <= hh < 24 and 0 <= mm < 60 else None
    return t, pase_id


def parse_cartelera(html: str) -> list[ScrapedEvent]:
    """Parse one Renoir daily cartelera page into ScrapedEvents.

    One ScrapedEvent per (film × session): for each desktop film block, emit one
    event per `.pase-cartelera` showtime. Date comes from the page's selected
    day-picker option; the per-session pillalas `pase` id is the per-occurrence
    external_id. Every screening is category `film`."""
    soup = BeautifulSoup(html, "html.parser")
    start_date = _page_date(soup) or dt.date.today()

    events: list[ScrapedEvent] = []
    # Desktop variant only — each block is rendered 3× across responsive copies.
    for block in soup.select(".my-account-content.d-none.d-lg-block"):
        title, source_url = _block_title_and_url(block)
        if not title or not source_url:
            continue
        image_url = _block_image(block)
        description, meta_annotations = _block_meta(block)

        for pase in block.select(".pase-cartelera"):
            start_time, pase_id = _session_time(pase)
            if start_time is None or not pase_id:
                continue  # no reliable session/occurrence; skip rather than guess

            annotations = list(meta_annotations)
            tag = pase.select_one(".pase-cartelera-tag")
            if tag and tag.get_text(strip=True):
                annotations.append(_clean(tag.get_text(strip=True)))

            events.append(
                ScrapedEvent(
                    title=title,
                    start_date=start_date,
                    start_time=start_time,
                    source_url=source_url,
                    category_slugs=["film"],
                    price=DEFAULT_PRICE,
                    description=description,
                    image_url=image_url,
                    external_id=f"pase-{pase_id}",
                    annotations=annotations,
                )
            )

    return events


class RenoirFloridablancaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        seen: set[str] = set()
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            first = client.get(CARTELERA_URL).text
            dates = _available_dates(BeautifulSoup(first, "html.parser"))
            if not dates:
                dates = [dt.date.today() + dt.timedelta(days=i) for i in range(_FALLBACK_DAYS)]

            for i, day in enumerate(dates):
                html = first if i == 0 else client.get(
                    CARTELERA_URL, params={"fecha": day.isoformat()}
                ).text
                for ev in parse_cartelera(html):
                    # pase id is unique per session, so it dedups across day fetches.
                    if ev.external_id in seen:
                        continue
                    seen.add(ev.external_id)
                    events.append(ev)
        return events


register(
    scraper=RenoirFloridablancaScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Renoir Floridablanca",
        city_slug="barcelona",
        address="Carrer de Floridablanca, 135, L'Eixample, 08011 Barcelona",
        site_url="https://www.cinesrenoir.com/cine/renoir-floridablanca/",
        category_slugs=["film"],
        list_memberships=[
            ListMembership(list_slug="film"),
        ],
    ),
)
