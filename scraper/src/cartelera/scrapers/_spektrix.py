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
import logging
import re
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, CARTELITA_COMPAT_UA, fetch
from cartelera.scrapers.price import format_gbp_range
from cartelera.types import ScrapedEvent

logger = logging.getLogger(__name__)

# Performances further out than this are left for later runs (theatre seasons
# are announced ~6 months ahead; longer windows only add on-sale-later noise).
WINDOW_DAYS = 183
# Price-list requests in flight at once (one per distinct price list).
MAX_CONCURRENCY = 4
# Instances tried per price list before giving up on its price.
PRICE_ATTEMPTS = 3
TIMEOUT = 90

# Instance-level boolean attributes worth surfacing as annotations: access
# provision and the kind of performance (preview, post-show talk) — never
# box-office internals (press/writers' nights, schools, discounts). Names are
# per client; these are the ones seen across the London clients (2026-10).
ACCESS_FLAGS: dict[str, str] = {
    "Captioned": "captioned",
    "CaptionedPerformance": "captioned",
    "SLCaptioned": "captioned",  # Park Theatre's listing flags (SL…)
    "AudioDescribed": "audio described",
    "AudioDescribedPerformance": "audio described",
    "SLAudioDescribed": "audio described",
    "BSL": "BSL interpreted",
    "BSLInterpreted": "BSL interpreted",
    "BSLPerformance": "BSL interpreted",
    "SignedBSLPerformance": "BSL interpreted",
    "SLSigned": "BSL interpreted",
    "Relaxed": "relaxed performance",
    "RelaxedPerformance": "relaxed performance",
    "RelaxedPerformanceInstance": "relaxed performance",
    "RelaxedAndSensoryAdapted": "relaxed performance",
    "SLRelaxed": "relaxed performance",
    "SensoryAdapted": "sensory adapted",
    "Chilled": "chilled performance",
    "AutismFriendly": "autism friendly",
    "DementiaFriendly": "dementia friendly",
    "ParentAndBaby": "parent and baby",
    "BabesInArms": "parent and baby",
    "TouchTour": "touch tour",
    "Preview": "preview",
    "PreviewPerformance": "preview",
    "PreviewInstance": "preview",
    "SLPreview": "preview",
    "PostShowTalk": "post-show talk",
    "AfterShowTalk": "post-show talk",
}

# Event -> our categories; [] means "not programme" (dropped).
Categorize = Callable[[dict], list[str]]
# (event, instance) -> our venue slug, for a client serving several of our
# venues; None drops the performance. The instance carries `venue` (the
# client's own venue record, {"name", "address", "id"}) when venues were
# looked up.
VenueOf = Callable[[dict, dict], "str | None"]
# A price-list entry ({"amount", "isBandDefault", "priceBand", "ticketType"})
# -> whether it counts towards the price (see price_text).
PriceBands = Callable[[dict], bool]
# (events, instances) -> None: a venue's own pass over the whole programme
# before curation (e.g. a join with its website, a label copied from the
# instances to their event). May mutate the dicts.
Prepare = Callable[[list[dict], list[dict]], None]
# (scraped, event, instance) -> None: a venue's own per-performance touch
# after the ScrapedEvent is built (a per-performance page, a price rule the
# price list can't express). Mutates `scraped`.
Finish = Callable[[ScrapedEvent, dict, dict], None]

# Spektrix ids as venue websites embed them: full ids ("571766ANTDSK…"), and
# the numeric ids of booking links ("/book/543497", "/book/instance/882636",
# "/book-online/…", "/tickets/351844", "EventInstanceId=…").
_SITE_IDS = (
    re.compile(r"\b(\d{4,8})A[A-Z]{20,40}\b"),
    re.compile(r"/book/(\d{4,8})\b"),
    re.compile(r"/book/instance/(\d{4,8})\b"),
    re.compile(r"/book-online/(\d{4,8})\b"),
    re.compile(r"/tickets/(\d{4,8})\b"),
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

    `listing_url` is one listing page or several (e.g. a theatre's what's-on
    and its cinema listings); a `sitemap.xml` works as a listing too (its
    `<loc>` URLs are absolute links). Show-page links are taken absolute or
    relative (resolved against their listing page); `link_pattern` is a
    regex the absolute show-page URL must match."""

    listing_url: str | tuple[str, ...]
    link_pattern: str
    required: bool = False
    impersonate: bool = False

    @property
    def listing_urls(self) -> tuple[str, ...]:
        return (self.listing_url,) if isinstance(self.listing_url, str) else tuple(self.listing_url)


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


def fetch_plans(client: Client, instances: list[dict], http: httpx.Client) -> dict[str, dict]:
    """Seating-plan id → {"name": the plan's own name, "venue": the client's
    venue record ({"name", "address", "id"}, {} when unknown)}:
    `/plans/{id}` names the plan and its venue, `/venues` describes it."""
    resp = http.get(f"{client.api}/venues")
    resp.raise_for_status()
    venues = {v["id"]: v for v in resp.json()}
    out: dict[str, dict] = {}
    for plan_id in dict.fromkeys(i["planId"] for i in instances if i.get("planId")):
        resp = http.get(f"{client.api}/plans/{plan_id}")
        resp.raise_for_status()
        plan = resp.json()
        venue_id = (plan.get("venue") or {}).get("id")
        out[plan_id] = {"name": (plan.get("name") or "").strip(), "venue": venues.get(venue_id, {})}
    return out


def fetch_plan_venues(client: Client, instances: list[dict], http: httpx.Client) -> dict[str, dict]:
    """Seating-plan id → the client's venue record ({"name", "address",
    "id"}). This is how a client that sells several buildings tells them
    apart."""
    return {pid: plan["venue"] for pid, plan in fetch_plans(client, instances, http).items() if plan["venue"]}


def assign_plans(client: Client, instances: list[dict], http: httpx.Client) -> None:
    """Give every instance its `venue` (the client's venue record, {} when
    unknown) and `plan` ({"name"}, {} when unknown), from its seating plan."""
    plans = fetch_plans(client, instances, http)
    for inst in instances:
        plan = plans.get(inst.get("planId"), {})
        inst["venue"] = plan.get("venue", {})
        inst["plan"] = {"name": plan["name"]} if plan else {}


def band(price: dict) -> str:
    """A price-list entry's seating band name, stripped ("" when absent)."""
    return ((price.get("priceBand") or {}).get("name") or "").strip()


def price_text(price_list: dict, bands: PriceBands | None = None) -> str | None:
    """A performance's price list → house convention.

    Uses each band's default ticket type (`isBandDefault`: the standard
    full-price ticket per seating band), so concession/member/access tiers
    don't widen the range; the 2x rule of `format_gbp_range` then decides
    between the top price and a "£lo–hi" range. All zero → "free"; no prices
    → None.

    `bands` is a venue's filter on the entries, applied first, for a price
    structure the band-default rule gets wrong (a membership allocation or a
    concession band flagged band-default; e.g. `lambda p: band(p) != "Y"`).
    When it keeps no paid price (nothing, or only £0 entries), the list
    isn't the structure the filter is for, and the whole list is used."""
    prices = price_list.get("prices") or []
    if bands:
        kept = [p for p in prices if bands(p)]
        if any((p.get("amount") or 0) > 0 for p in kept):
            prices = kept
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


def fetch_prices(
    client: Client, instances: list[dict], http: httpx.Client, bands: PriceBands | None = None
) -> dict[str, str | None]:
    """Price text per price-list id (`price_text`, with the venue's `bands`
    filter), asked of one of its instances. An instance that isn't on sale
    (online booking closed, not yet released) answers 404, so on-sale
    instances are asked first, up to PRICE_ATTEMPTS of them. A failed lookup
    is just an unknown price, never a failed run."""
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
                return pl, price_text(resp.json(), bands)
            except (httpx.HTTPError, ValueError):
                return pl, None
        return pl, None

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        return dict(pool.map(one, candidates.items()))


def embedded_ids(html: str) -> set[str]:
    """The numeric Spektrix ids a page embeds (see _SITE_IDS)."""
    return {m.group(1) for pattern in _SITE_IDS for m in pattern.finditer(html)}


def listing_links(listing: str, listing_url: str, link_pattern: str) -> list[str]:
    """Show-page URLs a listing page links, in order: absolute URLs anywhere
    in the text (also a sitemap's `<loc>`s), then relative `href`s resolved
    against the listing's URL — each kept when it fully matches
    `link_pattern`."""
    absolute = (m.group(0) for m in re.finditer(r"https?://[^\s\"'<>#?]+", listing))
    relative = (urljoin(listing_url, h) for h in re.findall(r"""href\s*=\s*["']([^"'#?\s]+)""", listing))
    return [u for u in dict.fromkeys([*absolute, *relative]) if re.fullmatch(link_pattern, u)]


def site_page_ids(site: Site) -> dict[str, set[str]]:
    """Show-page URL → the numeric Spektrix ids found on it. A listing that
    can't be fetched fails the run (the join, maybe curation, depends on it);
    a show page that can't (a dead link) is skipped with a warning."""
    links: list[str] = []
    for listing_url in site.listing_urls:
        listing = fetch(listing_url, headers=CARTELITA_BROWSER_HEADERS, impersonate=site.impersonate)
        links += [u for u in listing_links(listing, listing_url, site.link_pattern) if u not in links]

    def ids(url: str) -> tuple[str, set[str] | None]:
        try:
            page = fetch(url, headers=CARTELITA_BROWSER_HEADERS, impersonate=site.impersonate)
        except Exception as exc:  # one dead show page isn't a broken source
            logger.warning("spektrix site join: skipping %s (%s)", url, exc)
            return url, None
        return url, embedded_ids(page)

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        return {url: found for url, found in pool.map(ids, links) if found is not None}


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


def access_annotations(instance: dict, text_attrs: tuple[str, ...] = ()) -> list[str]:
    """The labels of the instance's true ACCESS_FLAGS, then the text of its
    `text_attrs` (a client's free-text access/performance attributes, e.g.
    "BSL Performance", "Captioned Screening"), in order, without repeats."""
    labels = [label for name, label in ACCESS_FLAGS.items() if instance.get(f"attribute_{name}") is True]
    labels += [re.sub(r"\s+", " ", attr(instance, name)) for name in text_attrs]
    return [label for label in dict.fromkeys(labels) if label]


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
    annotation_attrs: tuple[str, ...] = (),
    finish: Finish | None = None,
) -> list[ScrapedEvent]:
    """One ScrapedEvent per selected performance. `title`/`url` let a venue
    override the event name (e.g. strip internal season prefixes) and point
    at its own website page instead of the Spektrix event page. `venue` is
    for a client serving several of our venues (a multi-venue source): the
    venue slug of a performance, from the client's own venue/room data.
    `annotation_attrs` names the client's free-text instance attributes to
    annotate with (see access_annotations); `finish` is a per-performance
    touch-up (see Finish)."""
    events: list[ScrapedEvent] = []
    for event, inst, cats in selected:
        start = dt.datetime.fromisoformat(inst["start"])
        name = title(event) if title else re.sub(r"\s+", " ", event["name"]).strip()
        scraped = ScrapedEvent(
            title=name,
            start_date=start.date(),
            start_time=start.time(),
            source_url=(url(event) if url else None) or event.get("webUrl") or client.booking_url(event),
            category_slugs=list(cats),
            price=prices.get((inst.get("priceList") or {}).get("id")),
            description=description(event),
            image_url=event.get("imageUrl") or None,
            external_id=inst["id"],
            annotations=access_annotations(inst, annotation_attrs),
            venue_slug=venue(event, inst) if venue else None,
        )
        if finish:
            finish(scraped, event, inst)
        events.append(scraped)
    return events


def scrape(
    client: Client,
    categorize: Categorize,
    *,
    today: dt.date | None = None,
    site: Site | None = None,
    page_ids: Mapping[str, set[str]] | None = None,
    title: Callable[[dict], str] | None = None,
    url: Callable[[dict], str | None] | None = None,
    venue: VenueOf | None = None,
    plan_venues: bool = False,
    prepare: Prepare | None = None,
    price_bands: PriceBands | None = None,
    annotation_attrs: tuple[str, ...] = (),
    finish: Finish | None = None,
) -> list[ScrapedEvent]:
    """The whole pipeline for one client: programme → (plan venues) →
    (prepare) → (site join) → curation → prices (only for the performances
    kept) → ScrapedEvents → (finish).

    - `plan_venues`: each instance gets its `venue` record and `plan` name
      (see assign_plans) before `venue` is asked;
    - `site`: the Site join; `page_ids` instead, when the module fetched the
      show pages itself (because it reads more from them than ids): show-page
      URL → its numeric Spektrix ids (`embedded_ids`), joined the same way,
      for links only;
    - `prepare`, `finish`: the venue's own passes (see Prepare, Finish);
    - `price_bands`: the venue's price-list filter (see price_text);
    - `annotation_attrs`: free-text instance attributes to annotate with."""
    today = today or dt.date.today()
    with http_client() as http:
        events, instances = fetch_programme(client, today, http)
        if plan_venues:
            assign_plans(client, instances, http)
        if prepare:
            prepare(events, instances)
        pages: dict[str, str] = {}
        if site:
            pages = site_urls(site_page_ids(site), events, instances)
            if site.required:
                categorize = _listed_only(categorize, pages)
        elif page_ids is not None:
            pages = site_urls(page_ids, events, instances)
        selected = select(events, instances, categorize, venue)
        prices = fetch_prices(client, [inst for _e, inst, _c in selected], http, price_bands)

    def page_url(event: dict) -> str | None:
        return (url(event) if url else None) or pages.get(event["id"])

    return build(client, selected, prices, title=title, url=page_url, venue=venue,
                 annotation_attrs=annotation_attrs, finish=finish)


def _listed_only(categorize: Categorize, pages: dict[str, str]) -> Categorize:
    return lambda event: categorize(event) if event["id"] in pages else []
