"""Barbican Centre (Hall, Theatre, The Pit, Cinemas 1–3) plus the other
buildings its box office sells: Milton Court and the Guildhall School's
Silk Street building (Guildhall School of Music & Drama), and LSO St Luke's.

One Spektrix client (`barbicancentre`, served on spektrix.barbican.org.uk)
sells all of them, so this is a multi-venue source on the shared `_spektrix`
helper (see barbican_SOURCE.md). Curation uses the box office's own data:

- `PrimaryArtForm` + `EventType` — Classical Music (concert types) →
  classical; Cinema (screening types) → film; Theatre (plays, Barbican's own
  theatre & dance productions) → theater (dance is filed under Theatre and
  has no structural label of its own, so it stays theater); music events
  outside Classical → by `EventGenre`: Jazz / Pop / Alternative and Indie /
  Western Folk Music. Talks, workshops, tours, exhibitions, add-ons,
  members-only screenings, `SuppEvent`s and Raymond Gubbay's commercial
  concerts are not programme;
- Cinema only: the film must be published on barbican.org.uk — the box office
  also carries unpublished test screenings that no attribute tells apart;
- the performance's seating plan → the client's venue (room) → our
  building. Off-site rooms (St Giles Cripplegate, Temple Church, Guildhall's
  Great Hall), the "Wildcard" duplicate plan and streamed/wildcard
  instances are dropped.

barbican.org.uk show pages carry their Spektrix event ids (a `dataLayer`
`eventInfo` block), so events link to the Barbican's own page and take its
title ("London Symphony Orchestra/Sir Antonio Pappano" rather than the box
office's bare "London Symphony Orchestra").
"""

from __future__ import annotations

import datetime as dt
import json
import re
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from urllib.parse import urlencode

import httpx

from cartelera.scrapers import _spektrix as spk
from cartelera.scrapers import register_source
from cartelera.scrapers.http import CARTELITA_BROWSER_HEADERS, fetch
from cartelera.types import ListMembership, ScrapedEvent, SourceDefinition, VenueDefinition

SOURCE_SLUG = "barbican"
BARBICAN = "barbican"
MILTON_COURT = "milton-court"
GUILDHALL = "guildhall-school-silk-street"
LSO_ST_LUKES = "lso-st-lukes"
CLIENT = spk.Client("barbicancentre", "https://spektrix.barbican.org.uk")

SITE = "https://www.barbican.org.uk"
# What's on, filtered to the art forms we take (the site's own facet ids):
# 6 classical music, 11 contemporary music, 16 cinema, 21 theatre & dance.
ART_FORMS = (6, 11, 16, 21)
# The listing is paginated (30 cards a page, ~16 pages for six months).
MAX_PAGES = 40

# The client's venue (room) names, from `/venues` via each plan → ours.
ROOMS: dict[str, str] = {
    "Barbican Hall": BARBICAN,
    "Barbican Theatre": BARBICAN,
    "The Pit": BARBICAN,
    "Cinema 1": BARBICAN,
    "Cinema 2": BARBICAN,
    "Cinema 3": BARBICAN,
    "Frobisher Auditorium 1": BARBICAN,
    "Fountain Room": BARBICAN,
    "Barbican Art Gallery": BARBICAN,
    "Conservatory": BARBICAN,
    "Club Stage, Level -1": BARBICAN,
    "Barbican Foyers": BARBICAN,
    "Milton Court Concert Hall": MILTON_COURT,
    "Milton Court Theatre": MILTON_COURT,
    "Milton Court Studio": MILTON_COURT,
    "Rehearsal Room 3, Milton Court": MILTON_COURT,
    "Silk Street Theatre": GUILDHALL,
    "Silk Street Theatre Unreserved": GUILDHALL,
    "Silk St Music Hall": GUILDHALL,
    "Guildhall School": GUILDHALL,
    "LSO St Luke's": LSO_ST_LUKES,
}
# Instance types that aren't a seat in one of the rooms: "wildcard" mirrors
# an LSO concert on a placeholder plan, "streaming" is the online ticket.
VIRTUAL_INSTANCES = {"wildcard", "streaming"}

CLASSICAL_TYPES = {
    "Orchestral", "Chamber", "Recital", "Choral", "Opera and Oratorio", "Concert",
    "Film and live music", "Multi-media Performance", "Big Band",
}
FILM_TYPES = {
    "Screening - Film", "Talk + Screening", "Relaxed Screening",
    "Screening + Workshop", "Concert + Film Screening + Talk",
}
# Barbican's own theatre & dance productions carry no EventType ("").
THEATRE_TYPES = {"", "Play - Classical", "Play - Modern", "Immersive", "Performance",
                 "Multi-media Performance"}
MUSIC_TYPES = {"Concert", "Big Band"}
GENRES: dict[str, str] = {
    "Jazz": "jazz",
    "Pop": "pop",
    "Alternative and Indie": "alternative",
    "Western Folk Music": "folk",
}
EXCLUDED_PROMOTERS = {"Raymond Gubbay"}


def categorize(event: dict) -> list[str]:
    """The box office's labels → our categories ([] = not programme)."""
    if any(event.get(f"attribute_{flag}") is True
           for flag in ("SuppEvent", "BasketAddOn", "MembersOnly")):
        return []
    if spk.attr(event, "SeasonPromoter") in EXCLUDED_PROMOTERS:
        return []
    art_form = spk.attr(event, "PrimaryArtForm")
    kind = spk.attr(event, "EventType")
    if art_form == "Classical Music":
        return ["classical"] if kind in CLASSICAL_TYPES else []
    if art_form == "Cinema":
        return ["film"] if kind in FILM_TYPES else []
    if art_form == "Theatre":
        return ["theater"] if kind in THEATRE_TYPES else []
    if kind in MUSIC_TYPES:
        genre = GENRES.get(spk.attr(event, "EventGenre"))
        return [genre] if genre else []
    return []


def curate(pages: dict[str, str]) -> spk.Categorize:
    """`categorize`, plus: a film counts only once barbican.org.uk publishes
    it (test screenings sit in the cinemas with a film's exact labels)."""

    def run(event: dict) -> list[str]:
        cats = categorize(event)
        if cats == ["film"] and event["id"] not in pages:
            return []
        return cats

    return run


def venue(event: dict, instance: dict) -> str | None:
    if spk.attr(instance, "InstanceType") in VIRTUAL_INSTANCES:
        return None
    return ROOMS.get((instance.get("venue") or {}).get("name", ""))


# --- barbican.org.uk -------------------------------------------------------


def listing_url(today: dt.date, page: int) -> str:
    end = today + dt.timedelta(days=spk.WINDOW_DAYS)
    params = [("dates[min]", today.isoformat()), ("dates[max]", end.isoformat())]
    params += [(f"af[{af}]", str(af)) for af in ART_FORMS]
    params.append(("page", str(page)))
    return f"{SITE}/whats-on?{urlencode(params)}"


def listing_links(html: str) -> list[str]:
    """Show-page URLs of a what's-on page's cards, in order."""
    paths = []
    for tag in re.findall(r'<a\s[^>]*class="search-listing__link"[^>]*>', html):
        m = re.search(r'href="(/whats-on/[^"#?]+)"', tag)
        if m:
            paths.append(m.group(1))
    return list(dict.fromkeys(SITE + p for p in paths))


def page_info(html: str) -> dict | None:
    """A show page's analytics `dataLayer` entry — {"title", "subtitle",
    "eventInfo": [{"name", "id"}…]}: the Spektrix events the page sells —
    plus its `og:description` / `og:image` as "description" / "image" (the
    box office carries neither for programme events)."""
    m = re.search(r"dataLayer\s*=\s*(\[.*?\]);\s*</script>", html, re.S)
    if not m:
        return None
    try:
        layer = json.loads(m.group(1))
    except ValueError:
        return None
    if not layer or not isinstance(layer[0], dict):
        return None
    info = dict(layer[0])
    for key, prop in (("description", "og:description"), ("image", "og:image")):
        meta = re.search(rf'<meta\s+property="{prop}"\s+content="([^"]*)"', html)
        info[key] = unescape(meta.group(1)).strip() if meta else ""
    return info


def page_description(info: dict) -> str | None:
    """Subtitle (an LSO concert's programme, a show's company) + summary."""
    parts = [_norm(info.get("subtitle") or ""), _norm(info.get("description") or "")]
    return "\n\n".join(p for p in parts if p) or None


def join_pages(infos: dict[str, dict]) -> tuple[dict[str, str], dict[str, str]]:
    """(event id → show page, event id → the page's title). A page selling
    several events (a concert's paired performances, a member variant) is
    the page of each; when an event is on several pages the one selling the
    fewest events wins. The page title replaces the box-office name only when
    every event on the page has that same name (otherwise it would erase a
    variant: "Relaxed Screening: …")."""
    best: dict[str, tuple[int, str]] = {}
    titles: dict[str, str] = {}
    for url, info in infos.items():
        events = info.get("eventInfo") or []
        names = {_norm(e.get("name", "")) for e in events}
        title = _norm(info.get("title") or "")
        for e in events:
            eid = e.get("id")
            if not eid or (eid in best and best[eid][0] <= len(events)):
                continue
            best[eid] = (len(events), url)
            if title and len(names) == 1:
                titles[eid] = title
            else:
                titles.pop(eid, None)
    return {eid: url for eid, (_n, url) in best.items()}, titles


def fetch_site(today: dt.date) -> dict[str, dict]:
    """Show-page URL → its dataLayer entry, for every card of the paginated
    listing (stops at the first empty page; a page may repeat earlier cards —
    a long run is listed once per date — so "no new cards" is not the end)."""
    links: list[str] = []
    for page in range(MAX_PAGES):
        cards = listing_links(fetch(listing_url(today, page), headers=CARTELITA_BROWSER_HEADERS))
        if not cards:
            break
        links += [u for u in cards if u not in links]

    def one(url: str) -> tuple[str, dict | None]:
        try:
            return url, page_info(fetch(url, headers=CARTELITA_BROWSER_HEADERS))
        except Exception:  # an unpublished/broken page is just unjoined
            return url, None

    with ThreadPoolExecutor(max_workers=spk.MAX_CONCURRENCY) as pool:
        return {url: info for url, info in pool.map(one, links) if info}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# --- prices ------------------------------------------------------------------

# Price band "Y" is the Young Barbican allocation (the 16–29 scheme's £6–18
# tickets, sold as ticket type "Standard"): a membership tier, so it must not
# widen the range. Verified against the show pages' "Young Barbican £12".
MEMBER_BANDS = {"Y"}


def public_price_text(price_list: dict) -> str | None:
    """spk.price_text without the Young Barbican band."""
    prices = [p for p in price_list.get("prices") or []
              if (p.get("priceBand") or {}).get("name") not in MEMBER_BANDS]
    return spk.price_text({"prices": prices})


def fetch_prices(instances: list[dict], http: httpx.Client) -> dict[str, str | None]:
    """spk.fetch_prices (one request per price list, on-sale instances first,
    404 = off sale → try the next) with public_price_text. The helper has no
    price-list filter hook, hence this copy."""
    candidates: dict[str, list[str]] = {}
    for inst in sorted(instances, key=lambda i: not i.get("isOnSale")):
        pl = (inst.get("priceList") or {}).get("id")
        if pl and len(ids := candidates.setdefault(pl, [])) < spk.PRICE_ATTEMPTS:
            ids.append(inst["id"])

    def one(item: tuple[str, list[str]]) -> tuple[str, str | None]:
        pl, inst_ids = item
        for inst_id in inst_ids:
            try:
                resp = http.get(f"{CLIENT.api}/instances/{inst_id}/price-list")
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                return pl, public_price_text(resp.json())
            except (httpx.HTTPError, ValueError):
                return pl, None
        return pl, None

    with ThreadPoolExecutor(max_workers=spk.MAX_CONCURRENCY) as pool:
        return dict(pool.map(one, candidates.items()))


class BarbicanScraper:
    def scrape(self) -> list[ScrapedEvent]:
        """spk.scrape's pipeline (programme → plan venues → curation →
        prices → build), with the paginated site join and the member-band
        price filter, which the helper's `scrape` can't take."""
        today = dt.date.today()
        infos = fetch_site(today)
        pages, titles = join_pages(infos)
        with spk.http_client() as http:
            events, instances = spk.fetch_programme(CLIENT, today, http)
            by_plan = spk.fetch_plan_venues(CLIENT, instances, http)
            for inst in instances:
                inst["venue"] = by_plan.get(inst.get("planId"), {})
            selected = spk.select(events, instances, curate(pages), venue)
            prices = fetch_prices([inst for _e, inst, _c in selected], http)
        built = spk.build(
            CLIENT, selected, prices,
            title=lambda e: titles.get(e["id"]) or _norm(e["name"]),
            url=lambda e: pages.get(e["id"]),
            venue=venue,
        )
        return with_page_content(built, infos)


def with_page_content(events: list[ScrapedEvent], infos: dict[str, dict]) -> list[ScrapedEvent]:
    """Fill description/image from the event's barbican.org.uk page where the
    box office has none (it almost never does)."""
    for event in events:
        info = infos.get(event.source_url)
        if not info:
            continue
        event.description = event.description or page_description(info)
        event.image_url = event.image_url or info.get("image") or None
    return events


_MUSIC = ["classical", "jazz", "pop", "alternative", "folk"]


def _lists(categories: list[str]) -> list[ListMembership]:
    return [ListMembership(list_slug=c, whitelist_category_slug=c) for c in categories]


def _venue(slug: str, name: str, address: str, site_url: str, categories: list[str], **kw) -> VenueDefinition:
    return VenueDefinition(
        slug=slug, name=name, city_slug="london", address=address, site_url=site_url,
        category_slugs=categories, list_memberships=_lists(categories), **kw,
    )


register_source(
    BarbicanScraper(),
    SourceDefinition(
        slug=SOURCE_SLUG,
        name="Barbican",
        venues=[
            _venue(BARBICAN, "Barbican", "Silk Street, London EC2Y 8DS", SITE,
                   ["film", "theater", *_MUSIC],
                   instagram_url="https://www.instagram.com/barbicancentre"),
            _venue(MILTON_COURT, "Milton Court", "1 Milton Street, London EC2Y 9BH",
                   "https://www.gsmd.ac.uk", ["theater", *_MUSIC]),
            _venue(GUILDHALL, "Guildhall School (Silk Street)", "Silk Street, London EC2Y 8DT",
                   "https://www.gsmd.ac.uk", ["classical", "theater"]),
            _venue(LSO_ST_LUKES, "LSO St Luke's", "161 Old Street, London EC1V 9NG",
                   "https://www.lso.co.uk/lso-st-lukes", ["classical"]),
        ],
    ),
)
