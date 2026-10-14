from __future__ import annotations

import datetime as dt
import html as html_module
import json
import re

from cartelera.scrapers import register
from cartelera.scrapers._nl_common import USER_AGENT, eur_price, first_time
from cartelera.scrapers.http import fetch
from cartelera.types import ListMembership, ScrapedEvent, VenueDefinition

# Annabel (Schiestraat, Rotterdam) — concert hall + club. An Elementor
# WordPress site whose events are ordinary WP posts; the public REST API
# (`/wp-json/wp/v2/posts`) exposes each post's ACF fields: `start_date`
# (YYYYMMDD), `tijd` ("23:00 - 04:00" / "deuren open 19:00"), `ticketprijs`
# ("vanaf 33,-" / "33,75"), `Ticketstatus` (nieuw / uitverkocht),
# `muziekstijl` (genres), `calendar.cancelled|soldout`, plus the post's WP
# categories in `class_list`. One request. See annabel_SOURCE.md.
#
# Category = Annabel's own WP category: `concert` → pop, `clubnacht` → club
# (a post in both — a live band headlining a club night — gets both). Posts
# in neither (e.g. the `terras` category, Anna's terrace) are not programme.
API_URL = (
    "https://annabel.nu/wp-json/wp/v2/posts?per_page=100"
    "&_fields=id,link,title,class_list,acf,yoast_head_json.og_image"
)
VENUE_SLUG = "annabel"

CATEGORY_MAP = {"category-concert": "pop", "category-clubnacht": "club"}


def _price(acf: dict) -> str | None:
    status = acf.get("Ticketstatus") or ""
    status = " ".join(status) if isinstance(status, list) else str(status)
    calendar = acf.get("calendar") or {}
    if "uitverkocht" in status.lower() or calendar.get("soldout"):
        return "sold-out"
    raw = str(acf.get("ticketprijs") or "")
    if re.search(r"\bgratis\b|\bfree\b", raw, re.IGNORECASE):
        return "free"
    return eur_price(raw)


def _image(post: dict) -> str | None:
    images = (post.get("yoast_head_json") or {}).get("og_image") or []
    return images[0].get("url") if images else None


def parse_posts(posts: list[dict], today: dt.date) -> list[ScrapedEvent]:
    """REST posts → upcoming ScrapedEvents (pure; no network)."""
    events: list[ScrapedEvent] = []
    for post in posts:
        acf = post.get("acf") or {}
        if not isinstance(acf, dict):
            continue
        categories = [CATEGORY_MAP[c] for c in post.get("class_list") or [] if c in CATEGORY_MAP]
        categories = sorted(set(categories), key=["pop", "club"].index)
        if not categories:
            continue
        if (acf.get("calendar") or {}).get("cancelled"):
            continue
        raw_date = str(acf.get("start_date") or "")
        try:
            start_date = dt.datetime.strptime(raw_date, "%Y%m%d").date()
        except ValueError:
            continue
        if start_date < today:
            continue
        title = html_module.unescape((post.get("title") or {}).get("rendered") or "").strip()
        if not title:
            continue
        genres = acf.get("muziekstijl") or []
        annotations = [g for g in genres if isinstance(g, str) and g and g.lower() not in ("live", "club")]
        events.append(ScrapedEvent(
            title=title,
            start_date=start_date,
            start_time=first_time(acf.get("tijd")),
            source_url=post["link"],
            category_slugs=categories,
            price=_price(acf),
            image_url=_image(post),
            external_id=f"{post['id']}@{start_date.isoformat()}",
            annotations=annotations,
        ))
    return events


class AnnabelScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        posts = json.loads(fetch(API_URL, headers={"User-Agent": USER_AGENT}))
        return parse_posts(posts, dt.date.today())


register(
    scraper=AnnabelScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Annabel",
        city_slug="rotterdam",
        address="Schiestraat 20, 3013 AH Rotterdam",
        site_url="https://annabel.nu/",
        instagram_url="https://www.instagram.com/annabelrotterdam",
        category_slugs=["pop", "club"],
        list_memberships=[
            ListMembership(list_slug="pop", whitelist_category_slug="pop"),
            ListMembership(list_slug="club", whitelist_category_slug="club"),
        ],
    ),
)
