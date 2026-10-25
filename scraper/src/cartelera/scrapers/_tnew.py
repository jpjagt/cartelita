"""Tessitura TNEW v7 — shared by the London venues whose box office runs on it
(National Theatre, Shakespeare's Globe, Old Vic read the feed; Sadler's
Wells uses it as a cross-check; Southbank, Almeida and Hampstead are on TNEW
too, but their modules read the website alone — see tnew_SOURCE.md).

TNEW's event listing is fed by one undocumented-but-public call:

- `GET https://<host>/events` — any page will do; it hands out the session
  cookies (ASP.NET, Incapsula, and on hosts behind a Queue-it "safetynet" the
  Queue-it acceptance cookie — the plain client passes the safetynet; a real
  queue would show up as a failed POST);
- `POST https://<host>/api/products/productionseasons` with JSON
  `{"startDate": "YYYY-MM-DDT00:00", "endDate": "YYYY-MM-DDT00:00"}` →
  `{"productions": [...]}`: every production season (`productionSeasonId`,
  `productionTitle` as an HTML link, `listingImageUrl`) with its
  `performances` (`id`, `performanceDate` — venue-local wall time with its UK
  offset, `displayTime`, `performanceTitle`, `actionUrl` = `…/<prodSeasonId>/
  <perfId>`, `isOnSale`, `performanceStatusMessage` (free HTML: "Sold out",
  "<h2>SOLD OUT</h2>", "Tickets Not On Sale"…), `productTypeId` /
  `productTypeName` (host-defined product types; the name is usually empty,
  at the Old Vic it names the access provision)).

What TNEW does NOT carry: price, auditorium, genre (`keywords` is null on
every host) or a usable description. So every venue module joins the feed to
the venue's own website, whose booking links embed the TNEW ids
(`<host>/<prodSeasonId>/<perfId>`, `<host>/events/<prodSeasonId>`,
`<host>/overview/<prodSeasonId>`): the website decides what is programme
(curation), and gives title, page URL, price and room.

Private module (leading underscore): skipped by `load_all()`.
"""

from __future__ import annotations

import datetime as dt
import html as html_lib
import logging
import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, CARTELITA_BROWSER_UA, fetch
from cartelera.scrapers.price import format_gbp_range, gbp_amounts
from cartelera.types import ScrapedEvent

logger = logging.getLogger(__name__)

# Performances further out than this are left for later runs (as _spektrix).
WINDOW_DAYS = 183
# Website pages fetched at once (show pages of one venue).
MAX_CONCURRENCY = 3
TIMEOUT = 60
LONDON = ZoneInfo("Europe/London")

# A TNEW id pair or production id as venue websites embed them in booking
# links, on any host (the NT links "events.nationaltheatre.org.uk/events/<id>"
# while its TNEW host is tickets.nationaltheatre.org.uk).
_PERF_LINK = re.compile(r"https?://([a-z0-9.-]+)/(\d{3,7})/(\d{3,7})(?![\d/])")
_PROD_LINK = re.compile(r"https?://([a-z0-9.-]+)/(?:events|overview)/(\d{3,7})(?!\d)")


@dataclass(frozen=True)
class Performance:
    """One TNEW performance, flattened with its production."""

    production_id: str
    performance_id: str
    production_title: str  # plain text, whitespace collapsed
    title: str  # the performance's own title (may carry an access suffix)
    start: dt.datetime  # venue-local wall time, naive
    on_sale: bool
    status: str  # performanceStatusMessage as plain text ("" when none)
    product_type_id: int
    product_type_name: str
    url: str  # the TNEW booking page of this performance
    image_url: str | None = None

    @property
    def sold_out(self) -> bool:
        return "sold out" in self.status.lower()


@dataclass
class Booking:
    """The TNEW ids a website page links: performance pairs and bare
    production ids."""

    performances: set[tuple[str, str]] = field(default_factory=set)
    productions: set[str] = field(default_factory=set)

    @property
    def all_productions(self) -> set[str]:
        return self.productions | {prod for prod, _perf in self.performances}


def plain(text: str | None) -> str:
    """HTML fragment → plain text, whitespace collapsed ("" for None)."""
    if not text:
        return ""
    if "<" in text:
        text = BeautifulSoup(text, "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def fetch_productions(host: str, today: dt.date | None = None) -> list[dict]:
    """The raw `productions` of `host` with performances in [today, today +
    WINDOW_DAYS). Raises on any HTTP failure (a broken source, not an empty
    one)."""
    today = today or dt.date.today()
    end = today + dt.timedelta(days=WINDOW_DAYS)
    with httpx.Client(
        headers={"User-Agent": CARTELITA_BROWSER_UA},
        follow_redirects=True,
        timeout=TIMEOUT,
    ) as http:
        # Session cookies only; the page itself (or a Queue-it waiting room
        # it redirects to) is irrelevant.
        http.get(f"https://{host}/events")
        resp = http.post(
            f"https://{host}/api/products/productionseasons",
            json={"startDate": f"{today.isoformat()}T00:00", "endDate": f"{end.isoformat()}T00:00"},
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    productions = data.get("productions") if isinstance(data, dict) else None
    if not isinstance(productions, list):
        raise ValueError(f"TNEW {host}: unexpected productionseasons payload")
    return productions


def performances(productions: list[dict]) -> list[Performance]:
    """Every performance of `productions`, in start order. A production that
    sells two products at one time (seating types) appears once per
    (production, start)."""
    out: list[Performance] = []
    seen: set[tuple[str, dt.datetime]] = set()
    for prod in productions:
        prod_id = str(prod["productionSeasonId"])
        prod_title = plain(prod.get("productionTitle"))
        for perf in prod.get("performances") or []:
            if perf.get("isPerformanceVisible") is False:
                continue
            # `performanceDate` is UTC ("…+00:00" also in summer); the
            # venue-local wall time is its London time (= the local part of
            # `iso8601DateString` and the `displayTime`).
            start = dt.datetime.fromisoformat(perf["performanceDate"]).astimezone(LONDON).replace(tzinfo=None)
            if (prod_id, start) in seen:
                continue
            seen.add((prod_id, start))
            out.append(
                Performance(
                    production_id=prod_id,
                    performance_id=str(perf["id"]),
                    production_title=prod_title,
                    title=plain(perf.get("performanceTitle")) or prod_title,
                    start=start,
                    on_sale=bool(perf.get("isOnSale")),
                    status=plain(perf.get("performanceStatusMessage")),
                    product_type_id=int(perf.get("productTypeId") or 0),
                    product_type_name=plain(perf.get("productTypeName")),
                    url=perf.get("actionUrl") or "",
                    image_url=prod.get("listingImageUrl") or None,
                )
            )
    return sorted(out, key=lambda p: (p.start, p.production_id))


def fetch_performances(host: str, today: dt.date | None = None) -> list[Performance]:
    return performances(fetch_productions(host, today))


def booking_ids(html: str, hosts: Iterable[str]) -> Booking:
    """The TNEW ids `html` links on any of `hosts` (the TNEW host, plus any
    alias the venue's site links; see _PERF_LINK / _PROD_LINK)."""
    allowed = set(hosts)
    return Booking(
        performances={(m.group(2), m.group(3)) for m in _PERF_LINK.finditer(html) if m.group(1) in allowed},
        productions={m.group(2) for m in _PROD_LINK.finditer(html) if m.group(1) in allowed},
    )


def fetch_pages(urls: Iterable[str], *, impersonate: bool = False) -> dict[str, str]:
    """URL → HTML for each of `urls` (at most MAX_CONCURRENCY at once). A page
    that can't be fetched is skipped with a warning — one dead show page isn't
    a broken source; the listing that linked it is fetched by the caller and
    fails the run when it fails."""

    def one(url: str) -> tuple[str, str | None]:
        try:
            return url, fetch(url, headers=CARTELITA_BROWSER_HEADERS, impersonate=impersonate, timeout=TIMEOUT)
        except Exception as exc:
            logger.warning("tnew: skipping %s (%s)", url, exc)
            return url, None

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        return {url: page for url, page in pool.map(one, list(dict.fromkeys(urls))) if page is not None}


def price_range(amounts: Iterable[float]) -> str | None:
    """A list of £ amounts → house convention ("£lo–hi" when the spread is
    at least 2x, else the top price; zero → "free"; nothing → None)."""
    values = [a for a in amounts if a is not None]
    if not values:
        return None
    paid = [a for a in values if a > 0]
    if not paid:
        return "free"
    return format_gbp_range(min(paid), max(paid))


def ladder_price(lines: Iterable[str]) -> str | None:
    """Price ladders in prose ("£25, £36, £51", "£35/£45/£55/£65",
    "£19.50–£81.50") → one range over every amount (`price_range`)."""
    return price_range(a for line in lines for a in gbp_amounts(line))


def event(
    perf: Performance,
    *,
    title: str,
    source_url: str,
    category_slugs: list[str],
    price: str | None = None,
    description: str | None = None,
    image_url: str | None = None,
    annotations: Iterable[str] = (),
    venue_slug: str | None = None,
) -> ScrapedEvent:
    """The ScrapedEvent of one TNEW performance. A sold-out performance's
    price is "sold-out"; the TNEW performance id is the external id (one per
    occurrence); the host's product-type name (access provision at the Old
    Vic) joins the annotations."""
    labels = [*annotations]
    if perf.product_type_name:
        # "BSL Interpreted" → "BSL interpreted" (acronyms keep their case).
        labels.append(" ".join(w if w.isupper() else w.lower() for w in perf.product_type_name.split()))
    return ScrapedEvent(
        title=title,
        start_date=perf.start.date(),
        start_time=perf.start.time(),
        source_url=source_url,
        category_slugs=list(category_slugs),
        price="sold-out" if perf.sold_out else price,
        description=description or None,
        image_url=image_url or perf.image_url,
        external_id=perf.performance_id,
        annotations=[a for a in dict.fromkeys(labels) if a],
        venue_slug=venue_slug,
    )


def meta_description(soup: BeautifulSoup) -> str | None:
    """A page's own summary (`og:description`, else `description`)."""
    for attrs in ({"property": "og:description"}, {"name": "description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and (tag.get("content") or "").strip():
            return plain(tag["content"])
    return None


def meta_image(soup: BeautifulSoup) -> str | None:
    tag = soup.find("meta", attrs={"property": "og:image"})
    return (tag.get("content") or "").strip() or None if tag else None
