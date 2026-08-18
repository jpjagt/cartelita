from __future__ import annotations
import datetime as dt
import html as html_module
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Moscow Cinema (Kino Moskva), Yerevan. The homepage server-renders the whole
# 7-day schedule: a date strip (`.Schedule-date__item` → "Today 18.08") and one
# `div#schedule-N.ScheduleTable__wrapper` table per day whose rows carry time,
# film title+URL, hall, display language, age and AMD price. Film scrapers emit
# ONE ScrapedEvent per (film, day) with all of that day's sessions in
# `start_times`; external_id = `<slug>@<date>` keeps occurrences distinct across
# days. Detail pages (`/en/ongoing/<slug>`) add synopsis/poster/genre.
# See moscow_cinema_SOURCE.md.
BASE_URL = "https://www.moscowcinema.com"
HOME_URL = f"{BASE_URL}/en"
VENUE_SLUG = "moscow-cinema"

# The host sits behind Cloudflare and has been seen 403-ing plain clients; a
# desktop browser UA is cheap insurance (default httpx UA also worked 2026-08-18).
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_DDMM = re.compile(r"(\d{1,2})\.(\d{1,2})")
_TIME = re.compile(r"^\s*(\d{1,2}):(\d{2})")
_PRICE_INT = re.compile(r"\d[\d\s.,]*")


def _clean(text: str) -> str:
    # Collapse internal runs of whitespace too — the site's markup carries
    # newline-indented text inside single elements ("Action,\n  Family").
    return re.sub(r"\s+", " ", html_module.unescape(text).replace("\xa0", " ")).strip()


def _cell_text(row: Tag, selector: str) -> str | None:
    el = row.select_one(selector)
    if not el:
        return None
    text = _clean(el.get_text(" ", strip=True))
    return text or None


def _resolve_date(ddmm: str, today: dt.date) -> dt.date | None:
    """Resolve the strip's 'DD.MM' to a full date near `today`.

    The strip always covers today…today+6, so pick the candidate year
    (today's, previous or next — for the New Year rollover) that lands
    closest to today."""
    m = _DDMM.search(ddmm)
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    candidates = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidates.append(dt.date(year, month, day))
        except ValueError:
            continue
    if not candidates:
        return None
    return min(candidates, key=lambda d: abs((d - today).days))


def _parse_time(text: str | None) -> dt.time | None:
    m = _TIME.match(text or "")
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    return dt.time(hh, mm) if 0 <= hh < 24 and 0 <= mm < 60 else None


def _price_amount(price: str) -> int | None:
    m = _PRICE_INT.search(price)
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(0))
    return int(digits) if digits else None


def _format_price(prices: list[str]) -> str | None:
    """Collapse a day's session prices per the price convention.

    All equal → verbatim ("2000 ֏"). Differing tiers (regular vs VIP halls):
    a "lo–hi ֏" range only when hi ≥ 2×lo, else the single highest public
    price. (AMD, so the shared euro formatter doesn't apply.)"""
    distinct = list(dict.fromkeys(p for p in prices if p))
    if not distinct:
        return None
    if len(distinct) == 1:
        return distinct[0]
    amounts = [a for a in (_price_amount(p) for p in distinct) if a is not None]
    if len(amounts) < 2:
        return distinct[0]
    lo, hi = min(amounts), max(amounts)
    if hi >= 2 * lo:
        return f"{lo}–{hi} ֏"
    return f"{hi} ֏"


def _clean_language(text: str | None) -> str | None:
    if not text:
        return None
    # Verbatim except whitespace/trailing-comma noise (the site sometimes renders
    # "…subtitles: Armenian," with a dangling comma).
    return text.rstrip(" ,") or None


def _strip_dates(soup: BeautifulSoup, today: dt.date) -> dict[str, dt.date]:
    """Map schedule wrapper ids ("schedule-0"…) to resolved dates."""
    dates: dict[str, dt.date] = {}
    for item in soup.select(".Schedule-date__item[data-id]"):
        date_p = item.select_one("p.date")
        if not date_p:
            continue
        resolved = _resolve_date(_clean(date_p.get_text(" ", strip=True)), today)
        if resolved:
            dates[item["data-id"]] = resolved
    return dates


def parse_schedule(html: str, today: dt.date) -> list[ScrapedEvent]:
    """Parse the homepage's 7-day schedule into one ScrapedEvent per (film, day).

    Each day's `#schedule-N` table rows (time / title+href / hall / language /
    age / price) are grouped by film; `start_times` carries every session that
    day, `start_time` the earliest. Language and price cells are kept verbatim
    (price collapsed per the convention when sessions differ); hall names go to
    annotations. `today` anchors the strip's year-less DD.MM dates."""
    soup = BeautifulSoup(html, "html.parser")
    dates = _strip_dates(soup, today)

    # (slug, date) → accumulated sessions, in document order.
    groups: dict[tuple[str, dt.date], dict] = {}
    for wrapper in soup.select("div.ScheduleTable__wrapper[id]"):
        date = dates.get(wrapper["id"])
        if date is None:
            continue
        for row in wrapper.select("tbody tr"):
            link = row.select_one(".ScheduleTable__movie .movie-name a[href]")
            time = _parse_time(_cell_text(row, ".ScheduleTable__time span"))
            if not link or time is None:
                continue
            title = _clean(link.get_text(strip=True))
            href = link.get("href", "").split("?")[0].rstrip("/")
            if not title or not href:
                continue
            slug = href.rsplit("/", 1)[-1]

            group = groups.setdefault(
                (slug, date),
                {"title": title, "url": href, "times": [], "halls": [],
                 "langs": [], "prices": []},
            )
            group["times"].append(time)
            hall = _cell_text(row, ".ScheduleTable__hall span")
            if hall and hall not in group["halls"]:
                group["halls"].append(hall)
            lang = _clean_language(_cell_text(row, ".ScheduleTable__lang"))
            if lang and lang not in group["langs"]:
                group["langs"].append(lang)
            price = _cell_text(row, ".ScheduleTable__price")
            if price:
                group["prices"].append(price)

    events: list[ScrapedEvent] = []
    for (slug, date), g in groups.items():
        times = sorted(set(g["times"]))
        events.append(
            ScrapedEvent(
                title=g["title"],
                start_date=date,
                start_time=times[0],
                start_times=times,
                source_url=g["url"],
                category_slugs=["film"],
                price=_format_price(g["prices"]),
                language=" / ".join(g["langs"]) or None,
                annotations=list(g["halls"]),
                external_id=f"{slug}@{date.isoformat()}",
            )
        )
    return events


def parse_film_detail(html: str) -> dict:
    """Extract synopsis / poster / genre from a film's detail page.

    Returns {"description", "image_url", "genre"} (values may be None)."""
    soup = BeautifulSoup(html, "html.parser")

    description = None
    desc_el = soup.select_one(".description-item .lighten-txt")
    if desc_el:
        description = _clean(desc_el.get_text(" ", strip=True)) or None

    image_url = None
    og = soup.find("meta", attrs={"name": "og:image"}) or soup.find(
        "meta", attrs={"property": "og:image"}
    )
    if og and og.get("content"):
        image_url = _clean(og["content"]) or None

    genre = None
    for grid in soup.select(".fs18-13.d-grid"):
        parts = list(grid.stripped_strings)
        if len(parts) >= 2 and _clean(parts[0]) == "Genre":
            genre = _clean(" ".join(parts[1:])) or None
            break

    return {"description": description, "image_url": image_url, "genre": genre}


class MoscowCinemaScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with httpx.Client(follow_redirects=True, timeout=30, headers=_HEADERS) as client:
            events = parse_schedule(client.get(HOME_URL).text, dt.date.today())

            # One detail fetch per unique film enriches every one of its
            # day-events; a failed fetch degrades to schedule-only fields.
            details: dict[str, dict] = {}
            for url in dict.fromkeys(ev.source_url for ev in events):
                try:
                    details[url] = parse_film_detail(client.get(url).text)
                except httpx.HTTPError:
                    details[url] = {}

        for ev in events:
            detail = details.get(ev.source_url) or {}
            ev.description = detail.get("description")
            ev.image_url = detail.get("image_url")
            genre = detail.get("genre")
            if genre and genre not in ev.annotations:
                ev.annotations.append(genre)
        return events


register(
    scraper=MoscowCinemaScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Moscow Cinema",
        city_slug="yerevan",
        address="18 Abovyan St, 0001 Yerevan",
        site_url="https://www.moscowcinema.com",
        instagram_url="https://www.instagram.com/moscowcinema/",
        category_slugs=["film"],
        list_memberships=[
            ListMembership(list_slug="film"),
        ],
    ),
)
