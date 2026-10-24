"""St James's Church Piccadilly — free lunchtime recitals (Mon/Wed/Fri
1.10pm, donations welcome) and The Sixteen's residency.

The church's WordPress exposes its events at `/wp-json/wp/v2/event` with the
`event-category` taxonomy (see st_james_piccadilly_SOURCE.md). Curation is
that taxonomy alone: only **free-concerts** and **the-sixteen** are kept →
classical. The much larger `music` category also holds the hired-in
"Vivaldi Four Seasons by Candlelight" tourist series, services, talks and
markets — none of which are in the two kept categories, so they drop out
without looking at titles. Posts also filed under `past-events` are
dropped.

The REST `content.rendered` is the page body (its ACF fields are empty):
the hero's first paragraph states the date and time without a year
("Wednesday 25 November 1.10pm") — the year is the first one on/after the
post's publication whose weekday matches (`_yearless`). Price: "Free
admission" → free; a "Ticket pricing: Adult £10/Child £5" line → £; else
unknown (The Sixteen's own concerts sell through thesixteen.com).
"""

from __future__ import annotations

import datetime as dt
import html
import re

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import _yearless, register
from cartelera.scrapers.http import CARTELITA_COMPAT_UA
from cartelera.scrapers.price import gbp_price
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

VENUE_SLUG = "st-james-piccadilly"
SITE = "https://www.sjp.org.uk"
API = f"{SITE}/wp-json/wp/v2"
KEPT_CATEGORIES = ("free-concerts", "the-sixteen")
PAST_CATEGORY = "past-events"
MAX_PAGES = 20


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_post(post: dict, today: dt.date) -> ScrapedEvent | None:
    """One `event` post → its ScrapedEvent, or None when its date can't be
    read or has passed."""
    soup = BeautifulSoup(post["content"]["rendered"], "html.parser")
    details = soup.select_one(".hero__details")
    paragraphs = [_clean(p.get_text(" ")) for p in details.find_all("p")] if details else []
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        return None
    published = dt.datetime.fromisoformat(post["date"]).date()
    start_date = _yearless.parse(paragraphs[0], published)
    if start_date is None or start_date < today:
        return None
    body = _clean(soup.get_text(" "))
    price = None
    if re.search(r"(?i)\bfree (admission|entry)\b", body):
        price = "free"
    else:
        m = re.search(r"(?i)ticket pric\w*:?(.{0,80})", body)
        price = gbp_price(m.group(1)) if m else None
    image = soup.select_one(".hero__image .image img")
    return ScrapedEvent(
        title=_clean(post["title"]["rendered"]),
        start_date=start_date,
        start_time=_yearless.parse_time(paragraphs[0]),
        source_url=post["link"],
        category_slugs=["classical"],
        price=price,
        description=paragraphs[1] if len(paragraphs) > 1 else None,
        image_url=image.get("src") if image else None,
        external_id=str(post["id"]),
    )


def parse(posts: list[dict], past_category_id: int | None, today: dt.date) -> list[ScrapedEvent]:
    events = []
    for post in posts:
        if past_category_id is not None and past_category_id in (post.get("event-category") or []):
            continue
        event = parse_post(post, today)
        if event:
            events.append(event)
    return sorted(events, key=lambda e: (e.start_date, e.start_time or dt.time()))


def fetch_posts(client: httpx.Client) -> tuple[list[dict], int | None]:
    """(the kept categories' event posts, the past-events category id)."""
    resp = client.get(f"{API}/event-category", params={"slug": ",".join((*KEPT_CATEGORIES, PAST_CATEGORY))})
    resp.raise_for_status()
    ids = {c["slug"]: c["id"] for c in resp.json()}
    missing = [slug for slug in KEPT_CATEGORIES if slug not in ids]
    if missing:
        raise ValueError(f"sjp.org.uk: event categories gone: {missing}")
    posts: list[dict] = []
    page = 1
    while True:
        resp = client.get(f"{API}/event", params={
            "event-category": ",".join(str(ids[s]) for s in KEPT_CATEGORIES),
            "per_page": 100, "page": page,
        })
        resp.raise_for_status()
        posts += resp.json()
        if page >= int(resp.headers.get("X-WP-TotalPages") or 1) or page >= MAX_PAGES:
            return posts, ids.get(PAST_CATEGORY)
        page += 1


class StJamesPiccadillyScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        headers = {"User-Agent": CARTELITA_COMPAT_UA, "Accept": "application/json"}
        with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
            posts, past = fetch_posts(client)
        return parse(posts, past, dt.date.today())


register(
    scraper=StJamesPiccadillyScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="St James's Piccadilly",
        city_slug="london",
        address="197 Piccadilly, London W1J 9LL",
        site_url=SITE,
        instagram_url="https://www.instagram.com/stjamespiccadilly",
        category_slugs=["classical"],
        list_memberships=[ListMembership(list_slug="classical")],
    ),
)
