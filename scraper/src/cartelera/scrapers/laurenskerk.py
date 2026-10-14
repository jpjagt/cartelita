"""Laurenskerk Rotterdam — the medieval city church: organ concerts, choral
music (resident Laurens Vocaal), visiting ensembles.

WordPress, server-rendered. The agenda (`/agenda/?pagination=N`) lists
`.event-item` cards (date, title, tagline, image, ticket link → detail page
`/evenement/<slug>/`). Each detail page has the sidebar (`.event-single__date`
/ `__time` / `__price` / ticket button) and the venue's own categories
(`.event-single__categories a`). One request per event (~40). See
laurenskerk_SOURCE.md for the curation rules.
"""

from __future__ import annotations

import datetime as dt
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers.browser import BROWSER_HELPER_UA
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

BASE_URL = "https://laurenskerk.nl"
AGENDA_URL = BASE_URL + "/agenda/"
VENUE_SLUG = "laurenskerk"

# The venue's own categories that are its music programme.
MUSIC_CATEGORIES = {"orgelconcerten", "laurenskerk invites", "concerten", "laurens vocaal"}
# The church's own programme lines (always kept).
OWN_LINES = {"orgelconcerten", "laurenskerk invites", "laurens vocaal"}
# Services ("Herdenken en vieren" = commemorate & celebrate).
SERVICE_CATEGORIES = {"herdenken en vieren"}
# Generic ticket platforms: a "Concerten" event ticketed through one of these
# (rather than the church's own shop or the performing ensemble's site) is a
# hired-in franchise/tour (Candlelight via Fever, pop tours, tribute bands).
THIRD_PARTY_TICKETING = ("feverup.com", "mticket.eu", "ticketmatic.com", "stager.co",
                         "ticketmaster.", "eventbrite.")

_MONTHS = {
    "januari": 1, "january": 1, "februari": 2, "february": 2, "maart": 3, "march": 3,
    "april": 4, "mei": 5, "may": 5, "juni": 6, "june": 6, "juli": 7, "july": 7,
    "augustus": 8, "august": 8, "september": 9, "oktober": 10, "october": 10,
    "november": 11, "december": 12,
}
_DATE = re.compile(r"(\d{1,2})\s*(" + "|".join(_MONTHS) + r")\s*(\d{4})?", re.I)
_TIME = re.compile(r"\b(\d{1,2})[:.](\d{2})\b")
_EUR = re.compile(r"€\s*(\d+(?:[.,]\d{1,2})?)")
_SKIP_TIER = re.compile(r"vriend|t/m|tot \d|jong|student|cjp|korting|kind|65\+", re.I)


def _text(el: Tag | None) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def _lines(el: Tag | None) -> list[str]:
    if el is None:
        return []
    for br in el.find_all("br"):
        br.replace_with("\n")
    return [re.sub(r"\s+", " ", x).strip() for x in el.get_text("").split("\n") if x.strip()]


def parse_dates(text: str, today: dt.date) -> list[dt.date]:
    """"zondag 18 oktober 2026", "vrijdag 13 november2026", "woensdag 21
    oktober donderdag 22 oktober" (year inferred: next occurrence)."""
    out: list[dt.date] = []
    for m in _DATE.finditer(text):
        day, month = int(m.group(1)), _MONTHS[m.group(2).lower()]
        year = int(m.group(3)) if m.group(3) else None
        if year is None:
            year = today.year if (month, day) >= (today.month, today.day) else today.year + 1
        try:
            out.append(dt.date(year, month, day))
        except ValueError:
            continue
    return out


def parse_agenda(html: str) -> tuple[list[dict], str | None]:
    """An agenda page -> (cards, next page URL). Pure."""
    soup = BeautifulSoup(html, "html.parser")
    cards = []
    for item in soup.select(".event-item"):
        if "event-item--upcoming" in item.get("class", []):
            continue
        link = item.select_one(".event-item__body a[href]") or item.select_one("a[href]")
        if not link:
            continue
        img = item.select_one("img[data-lazy-src]") or item.select_one("noscript img[src]")
        cards.append({
            "url": link["href"],
            "title": _text(item.select_one(".event-item__title")),
            "tagline": _text(item.select_one(".event-item__editor")) or None,
            "image_url": (img.get("data-lazy-src") or img.get("src")) if img else None,
        })
    nxt = soup.select_one("nav.pagination a.next[href]")
    return cards, (nxt["href"] if nxt else None)


def parse_detail(html: str, today: dt.date) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    single = soup.select_one(".event-single") or soup
    date_el = single.select_one(".event-single__date span")
    time_lines = _lines(single.select_one(".event-single__time span"))
    price_lines = _lines(single.select_one(".event-single__price span"))
    ticket = single.select_one(".event-single__sidebar a.button[href]")
    cats = [_text(a) for a in single.select(".event-single__categories a")]
    start_times, end_time = parse_times(time_lines)
    body = _text(single.select_one(".event-single__body"))
    return {
        "title": _text(single.select_one("h1")) or None,
        "dates": parse_dates(_text(date_el), today),
        "start_times": start_times,
        "end_time": end_time,
        "price": parse_price(price_lines),
        "ticket_url": ticket["href"] if ticket else None,
        "categories": cats,
        # A service lists its officiant ("voorganger") among the credits.
        "is_service": bool(re.search(r"\bvoorganger\b", body, re.I)),
    }


_DOORS = re.compile(r"(?:deur(?:en)? open|inloop|kerk open)\D{0,12}\d{1,2}[:.]\d{2}", re.I)
_UNTIL = re.compile(r"\btot\s+(\d{1,2})[:.](\d{2})", re.I)


def parse_times(lines: list[str]) -> tuple[list[dt.time], dt.time | None]:
    """"20:00 uur tot 21:15 uur / inloop vanaf 19:30u" -> ([20:00], 21:15);
    two shows ("Aanvang 19:30 tot 20:15 … Aanvang 21:15 tot 22:00") -> both
    starts; door/walk-in times are ignored."""
    text = _DOORS.sub(" ", " | ".join(lines))
    ends = [dt.time(int(h), int(m)) for h, m in _UNTIL.findall(text)]
    text = _UNTIL.sub(" ", text)
    starts = sorted({dt.time(int(h), int(m)) for h, m in _TIME.findall(text) if int(h) < 24})
    return starts, (ends[0] if len(starts) == 1 and ends else None)


def parse_price(lines: list[str]) -> str | None:
    if not lines:
        return None
    joined = " ".join(lines).lower()
    if re.search(r"gratis|vrije toegang|toegang is vrij|vrij toegankelijk", joined):
        return "free"
    if "uitverkocht" in joined or "sold out" in joined:
        return "sold-out"
    if "pay what you can" in joined:
        return "pay what you can"
    # "Met vroegboekkorting €54,95 ipv € 90,-": the regular price is the "ipv".
    regular = re.search(r"\bipv\.?\s*€\s*(\d+(?:[.,]\d{1,2})?)", joined)
    if regular:
        lines = [f"€ {regular.group(1)}"]
    amounts = [float(a.replace(",", ".")) for ln in lines if not _SKIP_TIER.search(ln)
               for a in _EUR.findall(ln)]
    if not amounts:
        return None
    lo, hi = min(amounts), max(amounts)
    fmt = lambda v: (str(int(v)) if v == int(v) else f"{v:.2f}".replace(".", ","))  # noqa: E731
    if lo > 0 and hi >= 2 * lo:
        return f"{fmt(lo)}–{fmt(hi)}€"
    return "free" if hi == 0 else f"{fmt(hi)}€"


def keep(detail: dict) -> bool:
    cats = {c.lower() for c in detail["categories"]}
    if cats & SERVICE_CATEGORIES or detail["is_service"]:
        return False
    if not cats & MUSIC_CATEGORIES:
        return False  # Ademruimte (yoga), Overig (roller disco, fairs), exhibitions
    if cats & OWN_LINES:
        return True
    host = urlparse(detail["ticket_url"] or "").netloc.lower()
    return not any(p in host for p in THIRD_PARTY_TICKETING)


def build_events(card: dict, detail: dict) -> list[ScrapedEvent]:
    if not keep(detail):
        return []
    slug = urlparse(card["url"]).path.rstrip("/").rsplit("/", 1)[-1]
    events = []
    times = detail["start_times"]
    for d in detail["dates"]:
        hhmm = times[0].strftime("%H%M") if times else "0000"
        events.append(ScrapedEvent(
            title=card["title"] or detail["title"],
            start_date=d,
            start_time=times[0] if times else None,
            start_times=list(times),
            end_time=detail["end_time"],
            source_url=card["url"],
            category_slugs=["classical"],
            price=detail["price"],
            description=card["tagline"],
            image_url=card["image_url"],
            external_id=f"{slug}@{d.isoformat()}T{hhmm}",
            annotations=list(detail["categories"]),
        ))
    return events


class LaurenskerkScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        today = dt.date.today()
        events: dict[str, ScrapedEvent] = {}
        with httpx.Client(headers={"User-Agent": BROWSER_HELPER_UA}, timeout=30,
                          follow_redirects=True) as c:
            url: str | None = AGENDA_URL
            cards: dict[str, dict] = {}
            for _ in range(20):
                if not url:
                    break
                r = c.get(url)
                r.raise_for_status()
                page_cards, url = parse_agenda(r.text)
                for card in page_cards:
                    cards.setdefault(card["url"], card)
            for card in cards.values():
                r = c.get(card["url"])
                if r.status_code != 200:
                    continue
                for ev in build_events(card, parse_detail(r.text, today)):
                    if ev.start_date >= today:
                        events.setdefault(ev.external_id, ev)
        return list(events.values())


register(
    scraper=LaurenskerkScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Laurenskerk",
        city_slug="rotterdam",
        address="Grotekerkplein 15, 3011 GC Rotterdam",
        site_url=BASE_URL + "/",
        instagram_url="https://www.instagram.com/laurenskerkrotterdam",
        category_slugs=["classical"],
        list_memberships=[ListMembership(list_slug="classical", whitelist_category_slug="classical")],
    ),
)
