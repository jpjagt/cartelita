from __future__ import annotations
import datetime as dt
import html as html_module
import re

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Ulikhanyan Club (jazz club, Yerevan) runs on the Haytoms.am ticketing
# platform. `/en/buy-ticket` server-renders the whole upcoming agenda (a
# rolling week, one concert per night) as `.event-area` row cards: title,
# `.event-fee2` date/time (Armenian month names even on the EN page, NO year),
# description and image. Price is NOT in the page at all — it lives in the
# Haytoms seat map, fetched per event from `POST api.haytoms.am/get/ticket`
# with the page-embedded `haytoms_token` JWT and the card's `data-openticket`
# id. See ulikhanyan_club_SOURCE.md.
AGENDA_URL = "https://ulikhanyanclub.com/en/buy-ticket"
BASE_URL = "https://ulikhanyanclub.com"
TICKET_API_URL = "https://api.haytoms.am/get/ticket"
VENUE_SLUG = "ulikhanyan-club"

# `.event-fee2` month names are Armenian (nominative), e.g. "18  Օգոստոս  Երեքշաբթի 20:30".
_MONTHS_HY = {
    "Հունվար": 1, "Փետրվար": 2, "Մարտ": 3, "Ապրիլ": 4, "Մայիս": 5,
    "Հունիս": 6, "Հուլիս": 7, "Օգոստոս": 8, "Սեպտեմբեր": 9,
    "Հոկտեմբեր": 10, "Նոյեմբեր": 11, "Դեկտեմբեր": 12,
}
_FEE2 = re.compile(r"(\d{1,2})\s+(\S+)\s+\S+\s+(\d{1,2}):(\d{2})")
_EVENT_HREF = re.compile(r"buy-ticket/(\d+)")
_TOKEN = re.compile(r'haytoms_token\s*=\s*"([^"]+)"')
# The weekly jam session titles itself "JAM SESSION | HOUSE BAND | EVERY MONDAY".
_EVERY_DAY = re.compile(
    r"\bEVERY\s+(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)\b",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").strip()


def _resolve_date(day: int, month_hy: str, today: dt.date) -> dt.date | None:
    """Resolve a year-less (day, Armenian month) to a full date near `today`.

    The agenda only spans the coming days, so pick the candidate year (previous,
    current or next — for the New Year rollover) that lands closest to today."""
    month = _MONTHS_HY.get(month_hy)
    if month is None:
        return None
    candidates = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidates.append(dt.date(year, month, day))
        except ValueError:
            continue
    if not candidates:
        return None
    return min(candidates, key=lambda d: abs((d - today).days))


def _parse_fee2(text: str, today: dt.date) -> tuple[dt.date | None, dt.time | None]:
    m = _FEE2.search(text)
    if not m:
        return None, None
    date = _resolve_date(int(m.group(1)), m.group(2), today)
    hh, mm = int(m.group(3)), int(m.group(4))
    time = dt.time(hh, mm) if 0 <= hh < 24 and 0 <= mm < 60 else None
    return date, time


def parse_agenda(html: str, today: dt.date) -> list[ScrapedEvent]:
    """Parse the `/en/buy-ticket` list into ScrapedEvents (price left None —
    it comes from the Haytoms ticket API, see scrape()).

    One event per `.event-area` row card with a `h4.event-name a` link. The
    numeric id in the link is per-occurrence (each concert night has its own
    page), so it doubles as the external_id. `today` anchors the year-less
    Armenian dates."""
    soup = BeautifulSoup(html, "html.parser")

    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for row in soup.select(".event-area .row"):
        link = row.select_one("h4.event-name a[href]")
        if not link:
            continue
        m = _EVENT_HREF.search(link.get("href", ""))
        title = _clean(link.get_text(" ", strip=True))
        if not m or not title:
            continue
        event_id = m.group(1)
        if event_id in seen:
            continue
        seen.add(event_id)

        fee2 = row.select_one(".event-fee2")
        start_date, start_time = _parse_fee2(fee2.get_text() if fee2 else "", today)
        if start_date is None:
            continue  # no reliable date; skip rather than guess

        desc_el = row.select_one("p")
        description = _clean(desc_el.get_text()) if desc_el else None

        img = row.select_one(".event-feature2 img[src]")
        image_url = img.get("src") if img else None

        recurrence = _EVERY_DAY.search(title)
        recurrence_hint = f"every {recurrence.group(1).capitalize()}" if recurrence else None

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=f"{BASE_URL}/en/buy-ticket/{event_id}",
                category_slugs=["jazz"],
                description=description or None,
                image_url=image_url or None,
                external_id=event_id,
                recurrence_hint=recurrence_hint,
            )
        )

    return events


def parse_ticket_ids(html: str) -> dict[str, str]:
    """Map each card's event id (our external_id) to its Haytoms
    `data-openticket` widget id, used for the price lookup."""
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, str] = {}
    for row in soup.select(".event-area .row"):
        link = row.select_one("h4.event-name a[href]")
        button = row.select_one("[data-openticket]")
        if not link or not button:
            continue
        m = _EVENT_HREF.search(link.get("href", ""))
        ticket_id = str(button.get("data-openticket", "")).strip()
        if m and ticket_id:
            out[m.group(1)] = ticket_id
    return out


def parse_token(html: str) -> str | None:
    """The page-embedded short-lived Haytoms JWT (`var haytoms_token = "..."`)."""
    m = _TOKEN.search(html)
    return m.group(1) if m else None


def price_from_ticket(payload: dict) -> str | None:
    """Derive the display price from a Haytoms `get/ticket` seat-map payload.

    Every seat in `map.Levels[].Places[]` has an integer `Price` (AMD —
    `event_currency` is empty = platform default) and an `active` flag (seat
    still buyable). No active seats => "sold-out"; all prices 0 => "free";
    otherwise the single price, with a lo–hi range only when hi >= 2*lo."""
    levels = ((payload.get("map") or {}).get("Levels")) or []
    prices: list[int] = []
    any_active = False
    for level in levels:
        for place in level.get("Places") or []:
            price = place.get("Price")
            if isinstance(price, (int, float)):
                prices.append(int(price))
            if place.get("active"):
                any_active = True
    if not prices:
        return None
    if not any_active:
        return "sold-out"
    positive = [p for p in prices if p > 0]
    if not positive:
        return "free"
    lo, hi = min(positive), max(positive)
    if hi >= 2 * lo:
        return f"{lo}–{hi} AMD"
    return f"{hi} AMD"


class UlikhanyanClubScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        html = httpx.get(AGENDA_URL, follow_redirects=True, timeout=30).text
        events = parse_agenda(html, today=dt.date.today())
        token = parse_token(html)
        ticket_ids = parse_ticket_ids(html)
        if token:
            with httpx.Client(timeout=30) as client:
                for event in events:
                    ticket_id = ticket_ids.get(event.external_id or "")
                    if not ticket_id:
                        continue
                    # Best-effort enrichment: a failed seat-map call leaves that
                    # event's price None rather than aborting the whole run.
                    try:
                        resp = client.post(
                            TICKET_API_URL,
                            headers={"Auth": f"HaytomsToken {token}"},
                            data={"id": ticket_id},
                        )
                        resp.raise_for_status()
                        event.price = price_from_ticket(resp.json())
                    except (httpx.HTTPError, ValueError):
                        continue
        return events


register(
    scraper=UlikhanyanClubScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Ulikhanyan Club",
        city_slug="yerevan",
        address="7 Sayat-Nova Ave, Yerevan",
        site_url="https://ulikhanyanclub.com/en",
        # The site footer/header carry TWO different handles
        # (ulikhanyanjazzclub, ulikhanyanartclub); verified live which one is
        # the real active account — see SOURCE.md.
        instagram_url="https://www.instagram.com/ulikhanyanjazzclub",
        category_slugs=["jazz"],
        list_memberships=[
            ListMembership(list_slug="jazz"),
        ],
    ),
)
