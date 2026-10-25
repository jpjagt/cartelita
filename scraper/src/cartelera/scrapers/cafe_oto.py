"""Cafe OTO (Dalston) — London's home of experimental music and free improv.

Own site, server-rendered: the `/events/` list (12 items a page, `?page=N`
until no next link) carries date, time, title, the site's own prefix label
(presenter/series) and the full price ladder. Multi-day residencies show as
one date-range item ("1–2 November 2026"); their nights are read from the
residency's own page. robots.txt asks `Crawl-delay: 10`, so requests are
sequential with a 10 s pause (~5 list pages + one page per residency).
See cafe_oto_SOURCE.md.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
import time as time_mod
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.scrapers.http import CARTELITA_COMPAT_UA
from cartelera.scrapers.price import format_gbp, gbp_amounts
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

logger = logging.getLogger(__name__)

BASE_URL = "https://www.cafeoto.co.uk"
VENUE_SLUG = "cafe-oto"
TZ = ZoneInfo("Europe/London")
CRAWL_DELAY = 10  # robots.txt
MAX_PAGES = 15

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}

# "Saturday 24 October 2026, 7.30pm" / "Thursday 5 November 2026, 5.30–7pm"
_SINGLE_RE = re.compile(r"^(?:\w+\s+)?(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})(?:\s*,\s*(.+))?$")
# "1–2 November 2026" / "30 October – 1 November 2026"
_RANGE_RE = re.compile(r"^\d{1,2}(?:\s+[A-Za-z]+)?\s*[–-]\s*\d{1,2}\s+[A-Za-z]+\s+\d{4}$")
# "7.30pm", "2–5pm", "11am–6pm", "5.30–7pm", "9am"
_TIME_RE = re.compile(
    r"^(\d{1,2})(?:[.:](\d{2}))?\s*(am|pm)?"
    r"(?:\s*[–-]\s*(\d{1,2})(?:[.:](\d{2}))?\s*(am|pm))?",
    re.IGNORECASE,
)


def _clock(h: int, m: int, meridiem: str | None) -> dt.time | None:
    if meridiem:
        meridiem = meridiem.lower()
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if meridiem == "pm" else 0)
    if not (0 <= h < 24 and 0 <= m < 60):
        return None
    return dt.time(h, m)


def parse_times(text: str | None) -> tuple[dt.time | None, dt.time | None]:
    """"7.30pm" -> (19:30, None); "2–5pm" -> (14:00, 17:00); "11am–6pm" ->
    (11:00, 18:00). A start without am/pm takes the end's, unless that would
    put it after the end ("11.30–1pm" -> 11:30)."""
    if not text:
        return None, None
    m = _TIME_RE.match(text.strip())
    if not m:
        return None, None
    h1, m1, mer1, h2, m2, mer2 = m.groups()
    end = _clock(int(h2), int(m2 or 0), mer2) if h2 else None
    if mer1 is None and mer2 is not None:
        start = _clock(int(h1), int(m1 or 0), mer2)
        if start and end and start > end:
            start = _clock(int(h1), int(m1 or 0), "am")
    else:
        start = _clock(int(h1), int(m1 or 0), mer1)
    return start, end


def parse_date_header(text: str) -> tuple[dt.date, dt.time | None, dt.time | None] | None:
    m = _SINGLE_RE.match(" ".join(text.split()))
    if not m:
        return None
    month = _MONTHS.get(m.group(2).lower())
    if not month:
        return None
    try:
        date = dt.date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None
    start, end = parse_times(m.group(4))
    return date, start, end


def is_date_range(text: str) -> bool:
    return bool(_RANGE_RE.match(" ".join(text.split())))


def parse_price(spans: list[Tag]) -> str | None:
    """The price ladder -> the price convention.

    The first plain span is the door price ("£17"); "£15 Advance",
    "£12 (DICE)" are cheaper advance tiers, "£10 MEMBERS" and live-stream
    tickets are skipped. "SOLD OUT" -> "sold-out"; "Free Event" -> "free"."""
    amounts: list[float] = []
    texts: list[str] = []
    for sp in spans:
        text = " ".join(sp.get_text(" ", strip=True).split())
        texts.append(text.casefold())
        if "stream" in (sp.get("class") or []) or "MEMBER" in text.upper():
            continue
        amounts.extend(gbp_amounts(text))
    if any("sold out" in t for t in texts):
        return "sold-out"
    if amounts:
        return format_gbp(max(amounts))
    if any(t.startswith("free") for t in texts):
        return "free"
    return None


def _price_spans(container: Tag | None) -> list[Tag]:
    if container is None:
        return []
    # Only the top-level spans of the price block (members' links nest one).
    return [sp for sp in container.find_all("span") if sp.find_parent("span") is None]


def _slug(href: str) -> str:
    return href.strip("/").rsplit("/", 1)[-1]


def parse_list_page(html: str) -> tuple[list[dict], bool]:
    """One /events/?page=N -> (items, has a next page)."""
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    for it in soup.select("div.each-activity"):
        headers = it.select("div.each-header")
        if len(headers) < 2:
            continue
        date_text = " ".join(headers[0].get_text(" ", strip=True).split())
        link = headers[1].find("a")
        prefix_el = headers[1].select_one(".prefix")
        img = it.select_one(".each-image img")
        image_url = img.get("src") if img and (img.get("src") or "").startswith("http") else None
        price_block = it.select_one(".each-price")
        spans = _price_spans(price_block)
        items.append({
            "date_text": date_text,
            "title": " ".join(link.get_text(" ", strip=True).split()) if link else "",
            "href": (link.get("href") or "").strip() if link else "",
            "prefix": " ".join(prefix_el.get_text(" ", strip=True).split()) if prefix_el else "",
            "image_url": image_url,
            "spans": spans,
            "status": " ".join(s.get_text(" ", strip=True).casefold() for s in spans),
        })
    nxt = soup.select_one("#iscroll_other a[href*='page=']")
    return items, nxt is not None


def parse_residency_page(html: str) -> list[dict]:
    """A multi-day residency page -> its nights (date, times, title, href,
    price spans). The series-pass block (no dated link) is skipped."""
    soup = BeautifulSoup(html, "html.parser")
    nights: list[dict] = []
    for it in soup.select("div.activity-container div.each-activity"):
        header = it.select_one("div.each-header p")
        links = header.find_all("a") if header else []
        if len(links) < 2:
            continue
        nights.append({
            "date_text": " ".join(links[0].get_text(" ", strip=True).split()),
            "title": " ".join(links[1].get_text(" ", strip=True).split()),
            "href": (links[1].get("href") or "").strip(),
            "spans": _price_spans(it.select_one(".event-detail-meta")),
        })
    return nights


def _annotation(prefix: str) -> str | None:
    p = prefix.strip().rstrip(":").strip()
    return p or None


def build_event(
    date_text: str, title: str, href: str, spans: list[Tag], *,
    annotations: list[str], image_url: str | None,
) -> ScrapedEvent | None:
    parsed = parse_date_header(date_text)
    if parsed is None or not title or not href.startswith("/events/"):
        return None
    date, start, end = parsed
    return ScrapedEvent(
        title=title,
        start_date=date,
        start_time=start,
        start_times=[start] if start else [],
        end_time=end,
        source_url=BASE_URL + href,
        category_slugs=["alternative"],
        price=parse_price(spans),
        image_url=image_url,
        external_id=_slug(href),
        annotations=annotations,
    )


def keep_item(item: dict) -> bool:
    """Structural curation: drop items without an event page (e.g. "closed
    for private function"), cancelled ones, and OFFSITE shows (the site's
    own prefix label: they take place elsewhere)."""
    if not item["href"].startswith("/events/"):
        return False
    if "cancelled" in item["status"]:
        return False
    if item["prefix"].upper().startswith("OFFSITE"):
        return False
    return True


def events_from_items(items: list[dict], residencies: dict[str, str]) -> list[ScrapedEvent]:
    """List items (+ residency pages by href) -> events."""
    events: list[ScrapedEvent] = []
    seen: set[str] = set()

    def add(ev: ScrapedEvent | None) -> None:
        if ev is not None and ev.external_id not in seen:
            seen.add(ev.external_id)
            events.append(ev)

    for item in items:
        if not keep_item(item):
            continue
        ann = [a for a in [_annotation(item["prefix"])] if a]
        if is_date_range(item["date_text"]):
            html = residencies.get(item["href"])
            if html is None:
                continue
            nights = parse_residency_page(html)
            if not nights:
                logger.warning("cafe_oto: residency %s lists no nights", item["href"])
            for night in nights:
                if "cancelled" in " ".join(s.get_text(" ", strip=True).casefold() for s in night["spans"]):
                    continue
                add(build_event(night["date_text"], night["title"], night["href"], night["spans"],
                                annotations=ann + [item["title"]], image_url=item["image_url"]))
        else:
            ev = build_event(item["date_text"], item["title"], item["href"], item["spans"],
                             annotations=ann, image_url=item["image_url"])
            if ev is None:
                logger.warning("cafe_oto: unparseable item %r / %r", item["date_text"], item["title"])
            add(ev)
    return events


class CafeOtoScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        today = dt.datetime.now(TZ).date()
        headers = {"User-Agent": CARTELITA_COMPAT_UA}
        first = True
        with httpx.Client(headers=headers, follow_redirects=True, timeout=30) as client:
            def get(url: str) -> str:
                nonlocal first
                if not first:
                    time_mod.sleep(CRAWL_DELAY)
                first = False
                resp = client.get(url)
                resp.raise_for_status()
                return resp.text

            items: list[dict] = []
            for page in range(1, MAX_PAGES + 1):
                page_items, has_next = parse_list_page(get(f"{BASE_URL}/events/?page={page}"))
                items.extend(page_items)
                if not has_next:
                    break
            if not items:
                raise RuntimeError("cafe_oto: events list returned no items")
            residencies: dict[str, str] = {}
            for item in items:
                if keep_item(item) and is_date_range(item["date_text"]):
                    residencies[item["href"]] = get(BASE_URL + item["href"])
        return [e for e in events_from_items(items, residencies) if e.start_date >= today]


register(
    CafeOtoScraper(),
    VenueDefinition(
        slug=VENUE_SLUG,
        name="Cafe OTO",
        city_slug="london",
        address="18-22 Ashwin Street, London E8 3DL",
        site_url="https://www.cafeoto.co.uk",
        category_slugs=["alternative"],
        list_memberships=[ListMembership(list_slug="alternative")],
    ),
)
