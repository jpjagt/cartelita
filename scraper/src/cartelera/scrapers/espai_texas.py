from __future__ import annotations
import datetime as dt
import html as html_module
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Cinemes Texas / Espai Texas (Gràcia, Barcelona) server-renders a full-year
# calendar on its homepage: one `div.day[id="day_YYYY-MM-DD"]` per calendar day,
# each `have-events` day containing `.events-items > a.event`. Each anchor is one
# session/occurrence. The anchor's class is the category discriminator —
# `pelicula` (cinema), `espectacle` (theatre), `activitat` (activity); we keep
# only `pelicula`. One homepage request is the complete source (no JS, no
# pagination). See espai_texas_SOURCE.md.
HOME_URL = "https://espaitexas.cat/"
VENUE_SLUG = "espai-texas"

_DAY_ID = re.compile(r"day_(\d{4})-(\d{2})-(\d{2})")
_HOUR = re.compile(r"(\d{1,2}):(\d{2})")
# Trailing koobin session suffix on a slug: optional `-vo`/`-vosc`, then
# `-YYYYMMDD-HHMM`. Stripped to recover the bare film slug for the external_id.
_KOOBIN_SUFFIX = re.compile(r"-(?:vo|vosc)?-?\d{8}-\d{4}$")

# Catalan free-admission phrases (defensive: the calendar carries no price text
# today, but normalize if a session ever does).
_FREE_PHRASES = ("gratu", "entrada lliure", "entrada libre")


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").strip()


def _day_date(day: Tag) -> dt.date | None:
    m = _DAY_ID.search(day.get("id", ""))
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _event_time(anchor: Tag) -> dt.time | None:
    el = anchor.select_one(".event-time")
    if not el:
        return None
    m = _HOUR.search(el.get_text(strip=True))
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    if not (0 <= hh < 24 and 0 <= mm < 60):
        return None
    # The venue uses "00:00" as a "time not yet announced" placeholder (these are
    # the not-yet-bookable sessions linking to the /pelicula/ detail page). Treat
    # midnight as unknown rather than an actual 00:00 screening.
    if hh == 0 and mm == 0:
        return None
    return dt.time(hh, mm)


def _film_slug(href: str) -> str | None:
    """Recover the bare film slug from the anchor href.

    href is either a koobin booking URL
    (`.../ca/<slug>-[vo|vosc-]YYYYMMDD-HHMM`) or a venue detail page
    (`.../pelicula/<slug>/`). Returns the film slug used to build a per-occurrence
    external_id; not used as a source_url (koobin/detail slugs differ)."""
    if not href:
        return None
    path = href.split("?")[0].rstrip("/")
    last = path.rsplit("/", 1)[-1]
    if not last:
        return None
    return _KOOBIN_SUFFIX.sub("", last) or None


def _price_for(date: dt.date) -> str:
    """Cinema ticket price by day of week (published on /informacio-practica/).

    6€ Mon–Fri, 4€ Thursday (dia de l'espectador), 8€ Sat–Sun. The online +1€
    despesa de gestió is a booking fee, not the ticket price, so it is excluded."""
    wd = date.weekday()  # Mon=0 .. Sun=6
    if wd == 3:  # Thursday
        return "4€"
    if wd >= 5:  # Saturday / Sunday
        return "8€"
    return "6€"


def parse_agenda(html: str) -> list[ScrapedEvent]:
    """Parse the Espai Texas homepage calendar into film ScrapedEvents.

    One ScrapedEvent per `div.day a.event.pelicula` (cinema sessions only; theatre
    `espectacle` and `activitat` anchors are skipped). Date from the enclosing
    `day_YYYY-MM-DD` id, title from `.event-title`, local time from `.event-time`
    ("00:00" ⇒ unknown), source_url from the anchor href, price from the
    day-of-week rule, and a per-occurrence external_id (`<slug>@<date>T<HHMM>`)."""
    soup = BeautifulSoup(html, "html.parser")

    events: list[ScrapedEvent] = []
    for day in soup.select("div.day[id^='day_']"):
        start_date = _day_date(day)
        if start_date is None:
            continue
        for anchor in day.select("a.event.pelicula"):
            title_el = anchor.select_one(".event-title")
            title = _clean(title_el.get_text(" ", strip=True)) if title_el else ""
            if not title:
                continue
            source_url = (anchor.get("href") or "").strip() or None
            if not source_url:
                continue
            start_time = _event_time(anchor)

            slug = _film_slug(source_url) or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            time_part = start_time.strftime("%H%M") if start_time else "0000"
            external_id = f"{slug}@{start_date.isoformat()}T{time_part}"

            events.append(
                ScrapedEvent(
                    title=title,
                    start_date=start_date,
                    start_time=start_time,
                    source_url=source_url,
                    category_slugs=["film"],
                    price=_price_for(start_date),
                    external_id=external_id,
                )
            )

    return events


class EspaiTexasScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            html = client.get(HOME_URL).text
        events = parse_agenda(html)
        # The same film+date+time can appear once; guard against any accidental
        # duplicate anchors in the calendar markup.
        seen: set[str | None] = set()
        unique: list[ScrapedEvent] = []
        for ev in events:
            if ev.external_id in seen:
                continue
            seen.add(ev.external_id)
            unique.append(ev)
        return unique


register(
    scraper=EspaiTexasScraper(),
    venue=VenueDefinition(
        slug="espai-texas",
        name="Cinemes Texas",
        city_slug="barcelona",
        address="Carrer de Bailèn, 205, Gràcia, 08037 Barcelona",
        site_url="https://espaitexas.cat",
        category_slugs=["film"],
        list_memberships=[
            ListMembership(list_slug="film"),
        ],
    ),
)
