"""The Events Calendar ("Tribe") WordPress REST API — shared by dB's and BASIS.

`GET <site>/wp-json/tribe/events/v1/events?per_page=50` returns upcoming
events (server default window: today → +2 years), paginated via
`next_rest_url`. Each event is one occurrence with its own post `id`
(recurring series are expanded server-side into separate posts), so the
`id` is a valid per-occurrence `external_id`.

Fields used: `id`, `title` (HTML-escaped), `url`, `start_date`
("YYYY-MM-DD HH:MM:SS", site-local), `all_day`, `cost` / `cost_details.values`,
`categories[].name` (the site's own event categories), `tags[].name`,
`excerpt`/`description` (HTML), `image.url`, `status`.

Private module (leading underscore): skipped by `load_all()`.
"""

from __future__ import annotations

import datetime as dt
import html as html_module
import json
import re

from bs4 import BeautifulSoup

from cartelera.scrapers._eur import HEADERS, eur_amounts, format_eur, to_float
from cartelera.scrapers.http import fetch

API_PATH = "/wp-json/tribe/events/v1/events"
PER_PAGE = 50
_MAX_PAGES = 20


def events_url(site: str) -> str:
    return f"{site.rstrip('/')}{API_PATH}?per_page={PER_PAGE}"


def fetch_all(site: str) -> list[dict]:
    """Every upcoming event, following `next_rest_url` (capped)."""
    url: str | None = events_url(site)
    events: list[dict] = []
    for _ in range(_MAX_PAGES):
        if not url:
            break
        payload = json.loads(fetch(url, headers=HEADERS))
        events.extend(payload.get("events") or [])
        url = payload.get("next_rest_url")
    return events


def text(value: str | None) -> str:
    """HTML-escaped (and possibly tagged) API text → plain text."""
    if not value:
        return ""
    plain = BeautifulSoup(value, "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", html_module.unescape(plain)).strip()


def title(ev: dict) -> str:
    return text(ev.get("title"))


def category_names(ev: dict) -> list[str]:
    return [text(c.get("name")) for c in ev.get("categories") or []]


def tag_names(ev: dict) -> list[str]:
    return [text(t.get("name")) for t in ev.get("tags") or []]


def start(ev: dict) -> tuple[dt.date, dt.time | None]:
    """(date, time) from the site-local `start_date`; all-day → no time."""
    when = dt.datetime.strptime(ev["start_date"], "%Y-%m-%d %H:%M:%S")
    if ev.get("all_day"):
        return when.date(), None
    return when.date(), when.time()


def image_url(ev: dict) -> str | None:
    img = ev.get("image")
    return img.get("url") if isinstance(img, dict) else None


def cost_price(ev: dict) -> str | None:
    """Tribe's own cost field → house price convention, or None when unset.

    `cost_details.values` holds the numeric tiers (["0"] for "Gratis");
    the free-text `cost` covers sites that type "Gratis"/"Free"/"€ 12"."""
    values = [v for v in (ev.get("cost_details") or {}).get("values") or [] if v]
    nums: list[float] = []
    for v in values:
        try:
            nums.append(to_float(str(v)))
        except ValueError:
            continue
    cost = text(ev.get("cost"))
    low = cost.lower()
    if "uitverkocht" in low or "sold out" in low:
        return "sold-out"
    if nums:
        return format_eur(max(nums))
    if "gratis" in low or "free" in low:
        return "free"
    amounts = eur_amounts(cost)
    if amounts:
        return format_eur(max(amounts))
    return None
