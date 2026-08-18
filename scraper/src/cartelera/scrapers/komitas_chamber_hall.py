from __future__ import annotations
import datetime as dt
import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.types import (
    ListMembership,
    ScrapedEvent,
    ScrapedTranslation,
    VenueDefinition,
)

# Komitas Chamber Music House, Yerevan — a 300-seat chamber hall with a Baroque
# organ, operated by the National Center for Chamber Music SNCO. The venue has
# no site of its own; its programme is ticketed through toms.am (Impresario
# Productions), which runs a dedicated "place" page for the venue in two
# languages (am/en, no ru). Each listing links to a per-event "ticket" detail
# page whose <select id="id_samo"> exposes the *authoritative* schedule
# (date+time+id) — more trustworthy than the free-text "Time: HH:MM." sentence
# buried in the description (they can disagree; see komitas_chamber_hall_SOURCE.md).
# Canonical language is Armenian (hy — Yerevan's default locale), English is a
# translation. See komitas_chamber_hall_SOURCE.md for full field mapping.
VENUE_SLUG = "komitas-chamber-hall"
BASE_URL = "https://www.toms.am"
PLACE_PATH = "place/Komitas+Chamber+Music+House"

_NUM_RE = re.compile(r"\d{3,6}")
_SCHEDULE_OPTION_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})")


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    out = " ".join(text.split())
    return out or None


@dataclass
class _PlaceEvent:
    """One `.ticked_block` from a place-listing page, in one language."""
    ticket_id: str
    title: str
    ticket_url: str
    category_label: str | None
    date: dt.date | None
    price_raw: str | None
    description: str | None
    image_url: str | None


def format_price(raw: str | None) -> str | None:
    """AMD free text, hand-formatted per the project's 2x-range rule (NOT the
    EUR-specific format_eur_range helper). Extracts every digit run (>=3
    digits) from the raw price text; a genuinely large tier spread (high >=
    2x low) becomes a range, otherwise the single highest public tier."""
    if not raw:
        return None
    nums = [int(n) for n in _NUM_RE.findall(raw)]
    if not nums:
        return None
    lo, hi = min(nums), max(nums)
    if hi >= 2 * lo:
        return f"{lo}–{hi} AMD"
    return f"{hi} AMD"


def _extract_ticket_id(href: str | None) -> str | None:
    if not href:
        return None
    m = re.search(r"/ticket/(\d+)", href)
    return m.group(1) if m else None


def parse_place(html_text: str) -> list[_PlaceEvent]:
    """Parse a toms.am place-listing page into one _PlaceEvent per
    `.ticked_block` inside `.div_cont`. The top-of-page slideshow
    ("MOST IMPORTANT") is a site-wide promo carousel across every toms.am
    venue and is not selected here (`.ticked_block` only occurs in the
    venue-scoped listing)."""
    soup = BeautifulSoup(html_text, "html.parser")
    out: list[_PlaceEvent] = []
    for block in soup.select(".ticked_block"):
        title = _clean((block.select_one(".ticked_title") or block).get_text())
        if not title:
            continue

        links = block.select(".ticked_links a")
        category_label = _clean(links[0].get_text()) if links else None

        date_div = block.select_one(".ticked_date")
        date_val: dt.date | None = None
        price_raw: str | None = None
        if date_div:
            lines = [l.strip() for l in date_div.get_text("\n").split("\n") if l.strip()]
            if lines:
                try:
                    date_val = dt.date.fromisoformat(lines[0])
                except ValueError:
                    date_val = None
            if len(lines) > 1:
                price_raw = " ".join(lines[1:])

        desc_div = block.select_one(".ticked_desc")
        description: str | None = None
        image_url: str | None = None
        ticket_url: str | None = None
        if desc_div:
            img = desc_div.select_one("img")
            image_url = img.get("src") if img else None
            order_link = desc_div.select_one(".ticked_order a")
            if order_link:
                href = order_link.get("href")
                ticket_url = href
                order_div = desc_div.select_one(".ticked_order")
                if order_div:
                    order_div.decompose()
            description = _clean(desc_div.get_text(" "))

        if not ticket_url:
            continue
        ticket_id = _extract_ticket_id(ticket_url)
        if not ticket_id:
            continue

        out.append(
            _PlaceEvent(
                ticket_id=ticket_id,
                title=title,
                ticket_url=ticket_url,
                category_label=category_label,
                date=date_val,
                price_raw=price_raw,
                description=description,
                image_url=image_url,
            )
        )
    return out


def parse_schedule(html_text: str) -> list[tuple[str, dt.date, dt.time]]:
    """Parse a toms.am ticket detail page's `<select id="id_samo">` into
    (schedule_id, date, time) tuples — one per sellable session. This is the
    authoritative per-occurrence time source (see module docstring)."""
    soup = BeautifulSoup(html_text, "html.parser")
    select = soup.select_one("#id_samo")
    if not select:
        return []
    out: list[tuple[str, dt.date, dt.time]] = []
    for opt in select.select("option"):
        value = opt.get("value")
        text = _clean(opt.get_text())
        if not value or not text:
            continue
        m = _SCHEDULE_OPTION_RE.search(text)
        if not m:
            continue
        date_val = dt.date.fromisoformat(m.group(1))
        time_val = dt.time(int(m.group(2)), int(m.group(3)))
        out.append((value, date_val, time_val))
    return out


def merge_events(
    hy_events: list[_PlaceEvent],
    en_events: list[_PlaceEvent],
    schedules: dict[str, list[tuple[str, dt.date, dt.time]]],
) -> list[ScrapedEvent]:
    """Combine the canonical (hy) listing, the en listing (matched by ticket
    id, for translations), and the per-ticket schedule (matched by ticket id,
    for the authoritative date/time) into ScrapedEvents — one per session."""
    en_by_id = {e.ticket_id: e for e in en_events}
    out: list[ScrapedEvent] = []

    for hy in hy_events:
        en = en_by_id.get(hy.ticket_id)
        translations: list[ScrapedTranslation] = []
        if en and en.title:
            translations.append(
                ScrapedTranslation(
                    lang="en",
                    title=en.title,
                    description=en.description,
                    source_url=en.ticket_url,
                )
            )

        price = format_price(hy.price_raw) or (format_price(en.price_raw) if en else None)
        image_url = hy.image_url or (en.image_url if en else None)
        annotations = [hy.category_label] if hy.category_label else []

        sessions = schedules.get(hy.ticket_id) or []
        if sessions:
            for schedule_id, date_val, time_val in sessions:
                out.append(
                    ScrapedEvent(
                        title=hy.title,
                        start_date=date_val,
                        start_time=time_val,
                        start_times=[time_val],
                        source_url=hy.ticket_url,
                        category_slugs=["classical"],
                        price=price,
                        description=hy.description,
                        image_url=image_url,
                        external_id=f"komitas-schedule-{schedule_id}",
                        language=None,
                        annotations=annotations,
                        translations=translations,
                    )
                )
        elif hy.date is not None:
            # Fallback: detail page unreachable/unparseable — use the listing
            # page's bare date, time unknown.
            out.append(
                ScrapedEvent(
                    title=hy.title,
                    start_date=hy.date,
                    source_url=hy.ticket_url,
                    category_slugs=["classical"],
                    price=price,
                    description=hy.description,
                    image_url=image_url,
                    external_id=f"komitas-ticket-{hy.ticket_id}@{hy.date.isoformat()}",
                    language=None,
                    annotations=annotations,
                    translations=translations,
                )
            )
    return out


class KomitasChamberHallScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        hy_html = httpx.get(
            f"{BASE_URL}/am/{PLACE_PATH}", follow_redirects=True, timeout=30
        ).text
        en_html = httpx.get(
            f"{BASE_URL}/en/{PLACE_PATH}", follow_redirects=True, timeout=30
        ).text
        hy_events = parse_place(hy_html)
        en_events = parse_place(en_html)

        schedules: dict[str, list[tuple[str, dt.date, dt.time]]] = {}
        for ev in hy_events:
            try:
                detail_html = httpx.get(
                    f"{BASE_URL}/am/ticket/{ev.ticket_id}",
                    follow_redirects=True,
                    timeout=30,
                ).text
            except httpx.HTTPError:
                continue
            sessions = parse_schedule(detail_html)
            if sessions:
                schedules[ev.ticket_id] = sessions

        return merge_events(hy_events, en_events, schedules)


register(
    scraper=KomitasChamberHallScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Komitas Chamber Music House",
        city_slug="yerevan",
        address="1 Isahakyan St, Yerevan",
        site_url="https://www.toms.am/en/place/Komitas+Chamber+Music+House",
        category_slugs=["classical"],
        list_memberships=[ListMembership(list_slug="classical")],
    ),
)
