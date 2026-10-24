"""Spektrix public API v3 — shared by the London venues on a Spektrix box office.

Most London theatres, concert halls and arts centres sell through Spektrix,
whose read-only v3 API is public (no key, no Cloudflare on the API host):

- `GET {api}/events?instanceStart_from=…&instanceStart_to=…` — the client's
  events: `id`, `name`, `description`/`htmlDescription`, `imageUrl`, `webUrl`
  (usually empty), plus **client-defined `attribute_*` fields** (a venue's own
  genre/type/series labels — the structural signal each venue module curates
  on; their names differ per client).
- `GET {api}/instances?startFrom=…&startTo=…` — one row per performance:
  `id`, `event.id`, `start` (venue-local), `cancelled`, `priceList.id`, plus
  instance attributes (access flags such as `Captioned`).
- `GET {api}/instances/{id}/price-list` — the performance's ticket prices.

Always pass a date window: unfiltered, the big clients (Barbican, Soho
Theatre) time out. The API is the box office's view, not the public
programme: it also carries ancillaries (ice-cream pre-orders, touch tours,
"Secure My Booking", test events, staff lunches), so every venue module must
filter on one of the client's own attributes — or, where the client has no
usable label, on the venue's public website. See `spektrix_SOURCE.md`.

Private module (leading underscore): skipped by `load_all()`.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, CARTELITA_COMPAT_UA, fetch
from cartelera.scrapers.price import format_gbp_range
from cartelera.types import ScrapedEvent

# Performances further out than this are left for later runs (theatre seasons
# are announced ~6 months ahead; longer windows only add on-sale-later noise).
WINDOW_DAYS = 183
# Price-list requests in flight at once (one per distinct price list).
MAX_CONCURRENCY = 4
# Instances tried per price list before giving up on its price.
PRICE_ATTEMPTS = 3
TIMEOUT = 90

# Instance-level boolean attributes worth surfacing as annotations. Names are
# per client; these are the ones seen across London clients (2026-10).
ACCESS_FLAGS: dict[str, str] = {
    "Captioned": "captioned",
    "AudioDescribed": "audio described",
    "BSLInterpreted": "BSL interpreted",
    "Relaxed": "relaxed performance",
    "RelaxedPerformance": "relaxed performance",
    "Preview": "preview",
    "PostShowTalk": "post-show talk",
}

# Event -> our categories; [] means "not programme" (dropped).
Categorize = Callable[[dict], list[str]]
# (event, instance) -> our venue slug, for a client serving several of our
# venues; None drops the performance. The instance carries `venue` (the
# client's own venue record, {"name", "address", "id"}) when venues were
# looked up.
VenueOf = Callable[[dict, dict], "str | None"]

# Spektrix ids as venue websites embed them: full ids ("571766ANTDSK…"), and
# the numeric ids of booking links ("/book/543497", "EventInstanceId=…").
_SITE_IDS = (
    re.compile(r"\b(\d{4,8})A[A-Z]{20,40}\b"),
    re.compile(r"/book/(\d{4,8})\b"),
    re.compile(r"(?i)\bEvent(?:Instance)?Id=(\d{4,8})\b"),
)


@dataclass(frozen=True)
class Client:
    """A Spektrix client: its name (the path segment) and the host serving it
    (`system.spektrix.com`, or the venue's custom domain)."""

    name: str
    host: str = "https://system.spektrix.com"

    @property
    def api(self) -> str:
        return f"{self.host}/{self.name}/api/v3"

    def booking_url(self, event: dict) -> str:
        """The client's public Spektrix event page (lists every performance
        with a booking link) — the fallback when the venue's own page isn't
        known."""
        return f"{self.host}/{self.name}/website/EventDetails.aspx?EventId={numeric_id(event['id'])}"


@dataclass(frozen=True)
class Site:
    """The venue's own website, joined to its Spektrix programme: the
    what's-on page links each show's page, and each show page embeds the
    Spektrix ids of its performances (booking buttons). The join gives every
    event its page on the venue's site (instead of the bare Spektrix event
    page) and, with `required`, doubles as curation for a client without a
    usable label: only events the venue lists publicly are kept.

    `link_pattern` is a regex an absolute show-page URL must match."""

    listing_url: str
    link_pattern: str
    required: bool = False
    impersonate: bool = False


def numeric_id(spektrix_id: str) -> str:
    """"118056AKTSMRLCGMVPKPCRQTBNJSGPJQG" → "118056" (the id the Spektrix
    web pages use)."""
    m = re.match(r"\d+", spektrix_id)
    if not m:
        raise ValueError(f"unexpected Spektrix id {spektrix_id!r}")
    return m.group(0)


def attr(obj: dict, name: str) -> str:
    """A client-defined attribute as stripped text ("" when absent/null)."""
    value = obj.get(f"attribute_{name}")
    if value is None or value is False:
        return ""
    return str(value).strip()


def http_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": CARTELITA_COMPAT_UA, "Accept": "application/json"},
        follow_redirects=True,
        timeout=TIMEOUT,
    )


def fetch_programme(
    client: Client, today: dt.date, http: httpx.Client
) -> tuple[list[dict], list[dict]]:
    """(events, instances) with a performance in [today, today + WINDOW_DAYS)."""
    end = today + dt.timedelta(days=WINDOW_DAYS)
    events = http.get(
        f"{client.api}/events",
        params={"instanceStart_from": today.isoformat(), "instanceStart_to": end.isoformat()},
    )
    events.raise_for_status()
    instances = http.get(
        f"{client.api}/instances",
        params={"startFrom": today.isoformat(), "startTo": end.isoformat()},
    )
    instances.raise_for_status()
    return events.json(), instances.json()


def fetch_plan_venues(client: Client, instances: list[dict], http: httpx.Client) -> dict[str, dict]:
    """Seating-plan id → the client's venue record ({"name", "address",
    "id"}): `/plans/{id}` names the plan's venue, `/venues` describes it.
    This is how a client that sells several buildings tells them apart."""
    resp = http.get(f"{client.api}/venues")
    resp.raise_for_status()
    venues = {v["id"]: v for v in resp.json()}
    out: dict[str, dict] = {}
    for plan_id in dict.fromkeys(i["planId"] for i in instances if i.get("planId")):
        resp = http.get(f"{client.api}/plans/{plan_id}")
        resp.raise_for_status()
        venue_id = (resp.json().get("venue") or {}).get("id")
        if venue_id in venues:
            out[plan_id] = venues[venue_id]
    return out


def price_text(price_list: dict) -> str | None:
    """A performance's price list → house convention.

    Uses each band's default ticket type (`isBandDefault`: the standard
    full-price ticket per seating band), so concession/member/access tiers
    don't widen the range; the 2x rule of `format_gbp_range` then decides
    between the top price and a "£lo–hi" range. All zero → "free"; no prices
    → None."""
    prices = price_list.get("prices") or []
    amounts = [p.get("amount") for p in prices if p.get("isBandDefault")]
    if not amounts:
        amounts = [p.get("amount") for p in prices]
    amounts = [float(a) for a in amounts if a is not None]
    if not amounts:
        return None
    paid = [a for a in amounts if a > 0]
    if not paid:
        return "free"
    return format_gbp_range(min(paid), max(paid))


def fetch_prices(client: Client, instances: list[dict], http: httpx.Client) -> dict[str, str | None]:
    """Price text per price-list id, asked of one of its instances. An
    instance that isn't on sale (online booking closed, not yet released)
    answers 404, so on-sale instances are asked first, up to
    PRICE_ATTEMPTS of them. A failed lookup is just an unknown price, never
    a failed run."""
    candidates: dict[str, list[str]] = {}
    for inst in sorted(instances, key=lambda i: not i.get("isOnSale")):
        pl = (inst.get("priceList") or {}).get("id")
        if pl:
            ids = candidates.setdefault(pl, [])
            if len(ids) < PRICE_ATTEMPTS:
                ids.append(inst["id"])

    def one(item: tuple[str, list[str]]) -> tuple[str, str | None]:
        pl, inst_ids = item
        for inst_id in inst_ids:
            try:
                resp = http.get(f"{client.api}/instances/{inst_id}/price-list")
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                return pl, price_text(resp.json())
            except (httpx.HTTPError, ValueError):
                return pl, None
        return pl, None

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        return dict(pool.map(one, candidates.items()))


def site_page_ids(site: Site) -> dict[str, set[str]]:
    """Show-page URL → the numeric Spektrix ids found on it."""
    listing = fetch(site.listing_url, headers=CARTELITA_BROWSER_HEADERS, impersonate=site.impersonate)
    links = list(dict.fromkeys(
        m.group(0) for m in re.finditer(r"https?://[^\s\"'<>#?]+", listing)
        if re.fullmatch(site.link_pattern, m.group(0))
    ))

    def ids(url: str) -> tuple[str, set[str]]:
        page = fetch(url, headers=CARTELITA_BROWSER_HEADERS, impersonate=site.impersonate)
        return url, {m.group(1) for pattern in _SITE_IDS for m in pattern.finditer(page)}

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        return dict(pool.map(ids, links))


def site_urls(page_ids: dict[str, set[str]], events: list[dict], instances: list[dict]) -> dict[str, str]:
    """Event id → its show page: the page carrying the most of the event's
    (numeric) event/instance ids — a page may also link other shows'
    performances ("you may also like"), but never more of them than its own."""
    owner: dict[str, str] = {numeric_id(e["id"]): e["id"] for e in events}
    for inst in instances:
        owner[numeric_id(inst["id"])] = inst["event"]["id"]
    best: dict[str, tuple[int, str]] = {}
    for url, ids in page_ids.items():
        counts: dict[str, int] = {}
        for nid in ids:
            if nid in owner:
                counts[owner[nid]] = counts.get(owner[nid], 0) + 1
        for event_id, n in counts.items():
            if n > best.get(event_id, (0, ""))[0]:
                best[event_id] = (n, url)
    return {event_id: url for event_id, (_n, url) in best.items()}


def description(event: dict) -> str | None:
    """The plain-text `description`, else the text of `htmlDescription`."""
    text = (event.get("description") or "").strip()
    if not text:
        html = event.get("htmlDescription") or ""
        text = BeautifulSoup(html, "html.parser").get_text("\n").strip()
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text or None


def access_annotations(instance: dict) -> list[str]:
    return [label for name, label in ACCESS_FLAGS.items() if instance.get(f"attribute_{name}") is True]


def select(
    events: list[dict],
    instances: list[dict],
    categorize: Categorize,
    venue: VenueOf | None = None,
) -> list[tuple[dict, dict, list[str]]]:
    """(event, instance, categories) for every non-cancelled performance of a
    programme event (at one of our venues, when `venue` is given), in start
    order."""
    by_id = {e["id"]: e for e in events}
    cats_by_event: dict[str, list[str]] = {}
    out: list[tuple[dict, dict, list[str]]] = []
    for inst in sorted(instances, key=lambda i: i["start"]):
        if inst.get("cancelled"):
            continue
        event = by_id.get((inst.get("event") or {}).get("id"))
        if event is None:
            continue
        if event["id"] not in cats_by_event:
            cats_by_event[event["id"]] = categorize(event)
        cats = cats_by_event[event["id"]]
        if cats and (venue is None or venue(event, inst)):
            out.append((event, inst, cats))
    return out


def build(
    client: Client,
    selected: list[tuple[dict, dict, list[str]]],
    prices: dict[str, str | None],
    *,
    title: Callable[[dict], str] | None = None,
    url: Callable[[dict], str | None] | None = None,
    venue: VenueOf | None = None,
) -> list[ScrapedEvent]:
    """One ScrapedEvent per selected performance. `title`/`url` let a venue
    override the event name (e.g. strip internal season prefixes) and point
    at its own website page instead of the Spektrix event page. `venue` is
    for a client serving several of our venues (a multi-venue source): the
    venue slug of a performance, from the client's own venue/room data."""
    events: list[ScrapedEvent] = []
    for event, inst, cats in selected:
        start = dt.datetime.fromisoformat(inst["start"])
        name = title(event) if title else re.sub(r"\s+", " ", event["name"]).strip()
        events.append(
            ScrapedEvent(
                title=name,
                start_date=start.date(),
                start_time=start.time(),
                source_url=(url(event) if url else None) or event.get("webUrl") or client.booking_url(event),
                category_slugs=list(cats),
                price=prices.get((inst.get("priceList") or {}).get("id")),
                description=description(event),
                image_url=event.get("imageUrl") or None,
                external_id=inst["id"],
                annotations=access_annotations(inst),
                venue_slug=venue(event, inst) if venue else None,
            )
        )
    return events


def scrape(
    client: Client,
    categorize: Categorize,
    *,
    today: dt.date | None = None,
    site: Site | None = None,
    title: Callable[[dict], str] | None = None,
    url: Callable[[dict], str | None] | None = None,
    venue: VenueOf | None = None,
    plan_venues: bool = False,
) -> list[ScrapedEvent]:
    """The whole pipeline for one client: programme → (site join) → curation
    → prices (only for the performances kept) → ScrapedEvents. With
    `plan_venues`, each instance gets its `venue` record (see
    fetch_plan_venues) before `venue` is asked."""
    today = today or dt.date.today()
    with http_client() as http:
        events, instances = fetch_programme(client, today, http)
        pages: dict[str, str] = {}
        if site:
            pages = site_urls(site_page_ids(site), events, instances)
            if site.required:
                categorize = _listed_only(categorize, pages)
        if plan_venues:
            by_plan = fetch_plan_venues(client, instances, http)
            for inst in instances:
                inst["venue"] = by_plan.get(inst.get("planId"), {})
        selected = select(events, instances, categorize, venue)
        prices = fetch_prices(client, [inst for _e, inst, _c in selected], http)

    def page_url(event: dict) -> str | None:
        return (url(event) if url else None) or pages.get(event["id"])

    return build(client, selected, prices, title=title, url=page_url, venue=venue)


def _listed_only(categorize: Categorize, pages: dict[str, str]) -> Categorize:
    return lambda event: categorize(event) if event["id"] in pages else []
