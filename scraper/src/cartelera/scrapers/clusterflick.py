"""Clusterflick — London's curated cinemas, from Clusterflick's open data
(multi-venue WHITELIST source).

Clusterflick (https://clusterflick.com, GitHub org `clusterflick`, maintainer
Alistair Brown) is an open-source pipeline that scrapes every film showing in
London. Its repos — including the data repos whose release assets we read —
are MIT-licensed; credit: "Film listings data from Clusterflick
(clusterflick.com), MIT licence". We read the `data-transformed` stage: one
release asset per venue, a JSON list of items (`title` = the venue's raw
title, `url` = the venue's film page, `category`, `performances[]`).

Only the venues in `VENUES` are read (the editorial whitelist, see
docs/london.md "Film" + Decision 3); venues another London source owns
(Barbican, Kiln, Rich Mix, ...) are never on it. Only screening-type items
(`category` in KEEP_CATEGORIES) are kept — Clusterflick's own label, never
the title. Field map, exclusions and health rules: clusterflick_SOURCE.md.
"""
from __future__ import annotations

import datetime as dt
import logging
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

import httpx

from cartelera.scrapers import register_source
from cartelera.scrapers.http import CARTELITA_UA
from cartelera.types import (
    ListMembership,
    ScrapedEvent,
    SourceDefinition,
    VenueDefinition,
)

logger = logging.getLogger(__name__)

SOURCE_SLUG = "clusterflick"
ASSET_URL = "https://github.com/clusterflick/data-transformed/releases/latest/download/{asset}"
RELEASE_API_URL = "https://api.github.com/repos/clusterflick/data-transformed/releases/latest"
TZ = ZoneInfo("Europe/London")
MAX_CONCURRENCY = 3
# Clusterflick publishes several releases a day; a latest release older than
# this means its pipeline has stalled — fail so the health issue opens.
MAX_RELEASE_AGE = dt.timedelta(days=3)

# Clusterflick item categories that are screenings. Everything else (talk,
# quiz, tv, event, music, comedy, workshop, and any new label) is dropped —
# see clusterflick_SOURCE.md for why `talk` and `tv` are out.
KEEP_CATEGORIES = {"movie", "multiple-movies", "shorts"}

# Clusterflick accessibility flags -> annotation labels.
_ACCESSIBILITY = {
    "subtitled": "subtitled",
    "audioDescription": "audio-described",
    "hardOfHearing": "hard-of-hearing",
    "babyFriendly": "baby-friendly",
    "relaxed": "relaxed",
}


def _venue(slug: str, name: str, address: str, site_url: str,
           lat: float, lng: float) -> VenueDefinition:
    return VenueDefinition(
        slug=slug,
        name=name,
        city_slug="london",
        address=address,
        site_url=site_url,
        lat=lat,
        lng=lng,
        category_slugs=["film"],
        list_memberships=[ListMembership(list_slug="film")],
    )


# (Clusterflick asset name, venue). Addresses and coordinates come from
# Clusterflick's venue records (`data-combined` combined-data.json, release
# 2026-10-24), checked against the cinemas' own sites.
VENUE_ASSETS: list[tuple[str, VenueDefinition]] = [
    ("bfi.org.uk-southbank", _venue(
        "bfi-southbank", "BFI Southbank", "Belvedere Road, South Bank, London SE1 8XT",
        "https://whatson.bfi.org.uk", 51.50662, -0.11579)),
    ("princecharlescinema.com", _venue(
        "prince-charles-cinema", "Prince Charles Cinema", "7 Leicester Place, London WC2H 7BY",
        "https://princecharlescinema.com", 51.51149, -0.13019)),
    ("thegardencinema.co.uk", _venue(
        "the-garden-cinema", "The Garden Cinema", "39-41 Parker Street, London WC2B 5PQ",
        "https://www.thegardencinema.co.uk", 51.51631, -0.12133)),
    ("riocinema.org.uk", _venue(
        "rio-cinema", "Rio Cinema", "107 Kingsland High Street, London E8 2PB",
        "https://riocinema.org.uk", 51.54970, -0.07550)),
    ("phoenixcinema.co.uk", _venue(
        "phoenix-cinema", "Phoenix Cinema", "52 High Road, East Finchley, London N2 9PJ",
        "https://www.phoenixcinema.co.uk", 51.58853, -0.16390)),
    ("thelexicinema.co.uk", _venue(
        "the-lexi-cinema", "The Lexi Cinema", "194b Chamberlayne Road, London NW10 3JU",
        "https://thelexicinema.co.uk", 51.53778, -0.22251)),
    ("thearzner.com", _venue(
        "the-arzner", "The Arzner", "10 Bermondsey Square, London SE1 3UN",
        "https://thearzner.com", 51.49774, -0.08072)),
    ("actonecinema.co.uk", _venue(
        "actone-cinema", "ActOne Cinema", "The Old Library, 119-121 High Street, Acton, London W3 6NA",
        "https://actonecinema.co.uk", 51.50659, -0.26857)),
    ("thecastlecinema.com", _venue(
        "the-castle-cinema", "The Castle Cinema",
        "First floor, 64-66 Brooksby's Walk, Hackney, London E9 6DA",
        "https://thecastlecinema.com", 51.55147, -0.04326)),
    ("closeupfilmcentre.com", _venue(
        "close-up-film-centre", "Close-Up Film Centre", "97 Sclater Street, London E1 6HR",
        "https://www.closeupfilmcentre.com", 51.52364, -0.07204)),
    ("ica.art", _venue(
        "ica", "ICA", "The Mall, London SW1Y 5AH",
        "https://www.ica.art", 51.50607, -0.13116)),
    ("genesiscinema.co.uk", _venue(
        "genesis-cinema", "Genesis Cinema", "93-95 Mile End Road, Whitechapel, London E1 4UJ",
        "https://www.genesiscinema.co.uk", 51.52129, -0.05114)),
    ("thenickel.co.uk", _venue(
        "the-nickel", "The Nickel", "117-119 Clerkenwell Road, London EC1R 5BY",
        "https://thenickel.co.uk", 51.52174, -0.11188)),
    ("cinemamuseum.org.uk", _venue(
        "the-cinema-museum", "The Cinema Museum", "2 Dugard Way, Renfrew Road, London SE11 4TH",
        "https://www.cinemamuseum.org.uk", 51.49229, -0.10524)),
    ("curzon.com-soho", _venue(
        "curzon-soho", "Curzon Soho", "99 Shaftesbury Avenue, London W1D 5DY",
        "https://www.curzon.com/venues/soho/", 51.51271, -0.13059)),
    # Bertha DocHouse is the documentary screen inside Curzon Bloomsbury; it
    # has no asset of its own (its screenings carry the note "Programmed by
    # Bertha Dochouse", which becomes an annotation). One venue.
    ("curzon.com-bloomsbury", _venue(
        "curzon-bloomsbury", "Curzon Bloomsbury",
        "The Brunswick Centre, London WC1N 1AW",
        "https://www.curzon.com/venues/bloomsbury/", 51.52424, -0.12308)),
    # Second wave (decisions in clusterflick_SOURCE.md).
    ("institut-francais.org.uk", _venue(
        "cine-lumiere", "Ciné Lumière (Institut français)", "17 Queensberry Place, London SW7 2DT",
        "https://www.institut-francais.org.uk/cinema/", 51.49456, -0.17727)),
    ("regentstreetcinema.com", _venue(
        "regent-street-cinema", "Regent Street Cinema", "307 Regent Street, London W1B 2HW",
        "https://www.regentstreetcinema.com", 51.51698, -0.14287)),
    ("arthousecrouchend.co.uk", _venue(
        "arthouse-crouch-end", "ArtHouse Crouch End", "159A Tottenham Lane, London N8 9BT",
        "https://www.arthousecrouchend.co.uk", 51.58193, -0.12008)),
    ("thehorsehospital.com", _venue(
        "the-horse-hospital", "The Horse Hospital", "Colonnade, Bloomsbury, London WC1N 1JD",
        "https://www.thehorsehospital.com", 51.52279, -0.12442)),
]

VENUES: list[VenueDefinition] = [v for _, v in VENUE_ASSETS]


def _annotations(item: dict, perf: dict) -> list[str]:
    labels: list[str] = []
    if item.get("category") and item["category"] != "movie":
        labels.append(item["category"])  # "shorts" / "multiple-movies"
    fmt = perf.get("format") or {}
    if fmt.get("source"):
        labels.append(str(fmt["source"]))  # 35mm / 70mm / 16mm / vhs
    if fmt.get("dimension") == "3d":
        labels.append("3D")
    for line in (perf.get("notes") or "").splitlines():
        line = " ".join(line.split())
        if line:
            labels.append(line)  # "Sing Along", "Part of <season>", "Q&A" ...
    for key, label in _ACCESSIBILITY.items():
        if (perf.get("accessibility") or {}).get(key):
            labels.append(label)
    return list(dict.fromkeys(labels))


def parse_asset(items: list[dict], venue_slug: str, today: dt.date) -> list[ScrapedEvent]:
    """One venue's data-transformed asset -> one ScrapedEvent per screening
    (from `today` on, London time). Pure: no network."""
    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    dropped: dict[str, int] = {}
    for item in items:
        category = item.get("category")
        if category not in KEEP_CATEGORIES:
            dropped[str(category)] = dropped.get(str(category), 0) + 1
            continue
        title = " ".join((item.get("title") or "").split())
        url = item.get("url")
        if not title or not url:
            continue
        for perf in item.get("performances") or []:
            if perf.get("time") is None:
                continue
            start = dt.datetime.fromtimestamp(perf["time"] / 1000, dt.timezone.utc).astimezone(TZ)
            if start.date() < today:
                continue
            start_time = start.time().replace(second=0, microsecond=0)
            # The booking URL is per screening at most venues, but some reuse
            # one URL per film (BFI, Prince Charles, ICA): qualify with the time.
            booking = perf.get("bookingUrl") or url
            eid = f"{booking}@{start.strftime('%Y-%m-%dT%H:%M')}"
            if eid in seen:
                # The same screening listed under two items (seen at Ciné
                # Lumière): keep the first.
                continue
            seen.add(eid)
            sold_out = (perf.get("status") or {}).get("soldOut") is True
            events.append(ScrapedEvent(
                title=title,
                start_date=start.date(),
                start_time=start_time,
                start_times=[start_time],
                source_url=url,
                category_slugs=["film"],
                price="sold-out" if sold_out else None,
                external_id=eid,
                annotations=_annotations(item, perf),
                venue_slug=venue_slug,
            ))
    if dropped:
        logger.info("clusterflick: %s: dropped non-screening items %s", venue_slug, dropped)
    return events


def check_release_age(published_at: str, now: dt.datetime) -> None:
    """Raise if Clusterflick's latest release is stale (pipeline stalled)."""
    published = dt.datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    if now - published > MAX_RELEASE_AGE:
        raise RuntimeError(
            f"clusterflick: latest data-transformed release is from {published_at} "
            f"(older than {MAX_RELEASE_AGE.days} days) — the pipeline has stalled"
        )


class ClusterflickScraper:
    def _fetch_asset(self, client: httpx.Client, asset: str) -> list[dict] | None:
        try:
            resp = client.get(ASSET_URL.format(asset=asset), timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("clusterflick: asset %s failed: %s", asset, exc)
            return None
        if not isinstance(data, list):
            logger.warning("clusterflick: asset %s is not a list", asset)
            return None
        return data

    def _check_release(self, client: httpx.Client) -> None:
        # One API call per run (the unauthenticated limit is 60/h). If the API
        # is unavailable or rate-limited, carry on: the assets are the data.
        try:
            resp = client.get(RELEASE_API_URL, timeout=30,
                              headers={"Accept": "application/vnd.github+json"})
            resp.raise_for_status()
            published_at = resp.json()["published_at"]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.warning("clusterflick: release age check skipped: %s", exc)
            return
        check_release_age(published_at, dt.datetime.now(dt.timezone.utc))

    def scrape(self) -> list[ScrapedEvent]:
        today = dt.datetime.now(TZ).date()
        with httpx.Client(headers={"User-Agent": CARTELITA_UA}, follow_redirects=True) as client:
            self._check_release(client)
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
                assets = list(pool.map(lambda av: self._fetch_asset(client, av[0]), VENUE_ASSETS))
        failed = [a for (a, _), data in zip(VENUE_ASSETS, assets) if data is None]
        # One missing asset costs that venue its events (the per-venue health
        # rules catch it); most of them failing is a source failure.
        if len(failed) * 2 > len(VENUE_ASSETS):
            raise RuntimeError(
                f"clusterflick: {len(failed)}/{len(VENUE_ASSETS)} assets failed: {', '.join(failed)}"
            )
        events: list[ScrapedEvent] = []
        for (_, venue), data in zip(VENUE_ASSETS, assets):
            if data is not None:
                events.extend(parse_asset(data, venue.slug, today))
        if not events:
            raise RuntimeError("clusterflick: no screenings in any asset")
        return events


register_source(
    scraper=ClusterflickScraper(),
    source=SourceDefinition(slug=SOURCE_SLUG, name="Clusterflick", venues=VENUES),
)
