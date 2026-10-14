from __future__ import annotations

import datetime as dt
import re

from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers._nl_common import ENGLISH_MONTHS, first_time, get
from cartelera.scrapers.price import eur_price
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# Roodkapje (Keileweg, Rotterdam-M4H) — artist-run "communal living-room,
# project space & underground laboratory": DIY gigs, noise, punk, queer
# nights, plus exhibitions/residencies. WordPress (Divi); `/agenda/`'s
# "Coming up" list renders each event as `a.rk_event` with its Roodkapje
# category as a class (`rk_event_category_live` / `_art`), the date ("30
# October 2026"), location and title. The production page adds the time
# (ticket line "20:30-23:00" or "Start: 20:30" in the text) and ticket status.
# Low volume (a handful of shows ahead). See roodkapje_SOURCE.md.
#
# Category: Roodkapje's `live` category → alternative. Items only in `art`
# (exhibitions, open studios, residency presentations) are left out. Prices
# sit on Stager (bots disallowed) → None unless the page states one.
AGENDA_URL = "https://roodkapje.org/agenda/"
VENUE_SLUG = "roodkapje"

_DATE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
_START = re.compile(r"(?:start|aanvang)\s*:?\s*(\d{1,2}[:.]\d{2})", re.IGNORECASE)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _date(text: str) -> dt.date | None:
    m = _DATE.search(text)
    if not m or m.group(2).lower() not in ENGLISH_MONTHS:
        return None
    try:
        return dt.date(int(m.group(3)), ENGLISH_MONTHS[m.group(2).lower()], int(m.group(1)))
    except ValueError:
        return None


def _categories(a: Tag) -> set[str]:
    prefix = "rk_event_category_"
    return {c[len(prefix):] for c in a.get("class") or [] if c.startswith(prefix)}


def parse_agenda(html: str) -> list[dict]:
    """`/agenda/` → [{url, title, date, categories, image}] (pure)."""
    soup = BeautifulSoup(html, "html.parser")
    items: dict[str, dict] = {}
    for a in soup.select("a.rk_event[href]"):
        title_el = a.select_one(".rk_event_title")
        dates_el = a.select_one(".rk_event_dates")
        date = _date(_clean(dates_el.get_text(" "))) if dates_el else None
        if not title_el or date is None:
            continue
        items.setdefault(a["href"], {
            "url": a["href"],
            "title": _clean(title_el.get_text(" ")),
            "date": date,
            "categories": _categories(a),
            "image": a.get("data-thumbnail") or None,
        })
    return list(items.values())


def parse_detail(html: str) -> tuple[dt.time | None, str | None]:
    """A production page → (start time, price) (pure)."""
    soup = BeautifulSoup(html, "html.parser")
    ticket = _clean(" ".join(t.get_text(" ") for t in soup.select(".rk_event_ticket")))
    content_el = soup.select_one(".rk_event_content")
    content = content_el.get_text("\n") if content_el else ""
    m = _START.search(content)
    start = first_time(m.group(1)) if m else first_time(ticket)
    low = ticket.lower()
    if "sold out" in low or "uitverkocht" in low:
        price = "sold-out"
    elif re.search(r"\bfree\b|\bgratis\b", low):
        price = "free"
    else:
        # "20:30-23:00 | €10" / "tickets 15,-": drop the times, keep amounts.
        price = eur_price(re.sub(r"\d{1,2}[:.]\d{2}", " ", ticket))
    return start, price


def build_events(agenda_html: str, details: dict[str, str]) -> list[ScrapedEvent]:
    """Agenda items (+ production pages url → html) → ScrapedEvents (pure)."""
    events: list[ScrapedEvent] = []
    for item in parse_agenda(agenda_html):
        if "live" not in item["categories"]:
            continue
        start, price = parse_detail(details[item["url"]]) if item["url"] in details else (None, None)
        slug = item["url"].rstrip("/").rsplit("/", 1)[-1]
        events.append(ScrapedEvent(
            title=item["title"],
            start_date=item["date"],
            start_time=start,
            source_url=item["url"],
            category_slugs=["alternative"],
            price=price,
            image_url=item["image"],
            external_id=f"{slug}@{item['date'].isoformat()}",
        ))
    return events


class RoodkapjeScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        agenda = get(AGENDA_URL)
        details = {
            i["url"]: get(i["url"]) for i in parse_agenda(agenda) if "live" in i["categories"]
        }
        return build_events(agenda, details)


register(
    scraper=RoodkapjeScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Roodkapje",
        city_slug="rotterdam",
        address="Keileweg 10A, 3029 BS Rotterdam",
        site_url="https://roodkapje.org/",
        instagram_url="https://www.instagram.com/roodkapje_rotterdam",
        category_slugs=["alternative"],
        list_memberships=[
            ListMembership(list_slug="alternative", whitelist_category_slug="alternative"),
        ],
    ),
)
