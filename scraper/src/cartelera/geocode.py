"""Venue coordinates for the map: geocode venues via OpenStreetMap Nominatim.

Nominatim usage policy (https://operations.osmfoundation.org/policies/nominatim/):
an honest User-Agent, at most one request per second, and results cached —
here in the DB: a venue is looked up only while `venue.geocoded_at IS NULL`
(unless forced), and a miss is recorded too (geocoded_at set, lat/lng NULL),
so it isn't retried every night.

Explicit coordinates win: a code-defined VenueDefinition carrying `lat`/`lng`
is written by seed and never geocoded. That's the fix for a venue the
geocoder misses or places wrong.

Lookup per venue, each query restricted to the city's country:
  1. address queries (address_queries): the address plus the city name unless
     it already names it, then cleaned-up variants (house number suffixes like
     "26-1"/"55hs"/"12A" dropped, a leading place name like "Westergas, "
     dropped), a structured street + city search (copes with trailing noise
     like "casi Washington"), then the bare address (a venue just outside the city proper,
     e.g. "Ouddiemerlaan 104, 1111 HL Diemen"). A precise hit (building /
     house / POI) wins outright; the first street-level hit is kept.
  2. "<venue name>, <city name>" — only if the hit's own name matches the
     venue's (a distinctive shared word: "Sala Montjuïc" must not land on
     "Sala Apolo") and, when (1) found the street, it lies on/near it.
  3. otherwise the street-level hit from (1), if any.
A hit is accepted only if it is precise enough (a street, building or POI —
not the city, a district or a postcode area: Nominatim answering "Amsterdam"
with the city's own centre point is a miss) and within MAX_DISTANCE_KM of the
city centre.

The parsing / query / acceptance parts are pure; `geocode_venues` does the
I/O and takes an injectable HTTP getter and sleep for tests.
"""

from __future__ import annotations

import datetime as dt
import logging
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from cartelera.models import City, Venue
from cartelera.scrapers.http import CARTELITA_UA

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = f"{CARTELITA_UA} venue geocoding"
# Nominatim policy: max 1 request/second. In practice the public instance
# throttles (429) bursts at ~1/s, so stay well under it.
MIN_INTERVAL_S = 1.5
# On 429 (throttled): back off BACKOFF_429_S, doubling, at most RETRIES_429
# times (its Retry-After is usually 0, which is no help).
BACKOFF_429_S = 30.0
RETRIES_429 = 3
MAX_DISTANCE_KM = 35.0        # farther from the city centre = wrong match
# Nominatim place_rank: 26 = street, 28-30 = building / POI / house. Anything
# coarser (postcode ~21-25, suburb ~18-20, city ~16) doesn't locate a venue.
MIN_PLACE_RANK = 26
PRECISE_RANK = 28             # building / house number / POI
# A name-search hit must lie this close to the street the address resolved to.
NAME_NEAR_STREET_KM = 1.5
# Words too generic to identify a venue by name.
_GENERIC_WORDS = {
    "sala", "teatre", "teatro", "theater", "theatre", "cafe", "club", "kerk",
    "church", "jazz", "cinema", "cinemes", "cines", "cine", "music", "musica",
    "house", "huis", "centre", "center", "centro", "centrum", "concert", "hall",
    "zaal", "auditori", "espai", "casa", "bar", "the", "het", "de", "la", "el",
    "les", "del", "van", "and", "en", "y", "i", "amsterdam", "barcelona",
    "rotterdam", "utrecht", "yerevan", "asuncion", "state", "national",
    # street types (a street "Mashtots Street" vs "Mashtots Avenue")
    "street", "avenue", "road", "square", "carrer", "calle", "avinguda",
    "avenida", "passeig", "placa", "plaza", "rambla", "plein", "laan", "weg",
    "kade", "gracht", "փողոց", "պողոտա",
}
# A hit this close to the city centre AND coarse is the city itself; a precise
# hit there is fine (a venue can sit on the main square).
_CENTRE_EPS_KM = 0.05


@dataclass(frozen=True)
class CityCentre:
    lat: float
    lng: float
    country: str  # ISO 3166-1 alpha-2, lower case (Nominatim countrycodes)


# Every city in seed.CITIES needs an entry (a test enforces it).
CITY_CENTRES: dict[str, CityCentre] = {
    "barcelona": CityCentre(41.3874, 2.1686, "es"),
    "yerevan": CityCentre(40.1792, 44.4991, "am"),
    "amsterdam": CityCentre(52.3728, 4.8936, "nl"),
    "rotterdam": CityCentre(51.9225, 4.4792, "nl"),
    "utrecht": CityCentre(52.0907, 5.1214, "nl"),
    "asuncion": CityCentre(-25.2637, -57.5759, "py"),
    "london": CityCentre(51.5074, -0.1278, "gb"),
}


@dataclass(frozen=True)
class Hit:
    lat: float
    lng: float
    place_rank: int | None = None
    display_name: str = ""
    names: tuple[str, ...] = ()  # the place's own names (namedetails), if any


@dataclass
class GeocodeReport:
    hits: list[tuple[str, str, Hit]] = field(default_factory=list)   # (city, slug, hit)
    misses: list[tuple[str, str, str]] = field(default_factory=list)  # (city, slug, name)
    skipped: int = 0  # pending venues left for a later pass (budget exhausted)


# --- pure parts -------------------------------------------------------------

# A free-form query string, or a structured one ({"street": ..., "city": ...}).
Query = str | dict[str, str]


def address_queries(address: str | None, city_name: str) -> list[Query]:
    """The address queries to try, in order, deduplicated (none without an
    address): free-form variants, then a structured street + city search
    (copes with trailing noise like "casi Washington" or "Amsterdam
    Westpoort"), then the bare address."""
    addr = (address or "").strip().strip(",").strip()
    if not addr:
        return []
    variants = [addr, _plain_house_number(addr)]
    variants += [_from_street(v) for v in variants]
    queries: list[Query] = list(dict.fromkeys(
        v if _names_city(v, city_name) else f"{v}, {city_name}" for v in variants if v))
    if street := _street_part(addr):
        queries.append({"street": street, "city": city_name})
    if addr not in queries:
        queries.append(addr)
    return queries


def _street_part(addr: str) -> str | None:
    """'Elementenstraat 16, Amsterdam Westpoort' -> 'Elementenstraat 16';
    'C/ de les Hondures, 30, 08027 Barcelona' -> 'C/ de les Hondures 30'.
    None when no part carries a house number."""
    parts = [p.strip() for p in _from_street(_plain_house_number(addr)).split(",")]
    if not re.search(r"\d", ",".join(parts[:2])):
        return None
    if len(parts) > 1 and re.fullmatch(r"\d+", parts[1]) and not re.search(r"\d", parts[0]):
        return f"{parts[0]} {parts[1]}"
    if not re.search(r"\d", parts[0]):
        return None
    # "Rigakade 10 1013 BC Amsterdam" / "Defensa Nacional 737 casi Washington":
    # a street-first part ends at its house number
    m = re.match(r"(\D+?\s\d+)\b", parts[0])
    return m.group(1) if m else parts[0]


def name_query(name: str, city_name: str) -> str:
    return f"{name.strip()}, {city_name}"


def build_queries(name: str, address: str | None, city_name: str) -> list[Query]:
    """Every query locate() may try, in order."""
    return [*address_queries(address, city_name), name_query(name, city_name)]


_HOUSE_SUFFIX = re.compile(r"\b(\d+)(?:\s?[-–/]\s?[0-9A-Za-z]+|[A-Za-z]{1,3})\b")


def _plain_house_number(addr: str) -> str:
    """'Korte Leidsedwarsstraat 26-1' -> '... 26'; '55hs' -> '55'; '12A' -> '12'.
    Postcodes ('1017 PT', '08001') are left alone."""
    return _HOUSE_SUFFIX.sub(r"\1", addr)


def _from_street(addr: str) -> str:
    """Drop leading comma-separated parts before the street: 'Westergas,
    Pazzanistraat 4' -> 'Pazzanistraat 4'; 'Castell de Montjuïc, Carretera de
    Montjuïc, 66, ...' -> 'Carretera de Montjuïc, 66, ...'."""
    parts = [p.strip() for p in addr.split(",")]
    i = next((i for i, p in enumerate(parts) if re.search(r"\d", p)), None)
    if i is None:
        return addr
    if i > 0 and re.fullmatch(r"[\d\s\-–/]+", parts[i]):
        i -= 1  # "Street, 12": the street is the part before the number
    return ", ".join(parts[i:])


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[^\W_]+", _strip_accents(text).casefold())
            if len(w) >= 3 and w not in _GENERIC_WORDS}


def name_matches(venue_name: str, hit: Hit) -> bool:
    """Whether a name-search hit is plausibly the venue: one of its own names
    (namedetails, else the first part of display_name) shares a distinctive
    word with the venue's."""
    own = set().union(*(_words(n) for n in hit.names or (hit.display_name.split(",")[0],)))
    return bool(_words(re.sub(r"\(.*?\)", "", venue_name)) & own)


def _names_city(text: str, city_name: str) -> bool:
    fold = lambda s: _strip_accents(s).casefold()  # noqa: E731
    return fold(city_name) in fold(text)


def _strip_accents(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def parse_response(payload: object) -> Hit | None:
    """The first result of a Nominatim jsonv2 search, or None."""
    if not isinstance(payload, list) or not payload:
        return None
    first = payload[0]
    if not isinstance(first, dict):
        return None
    try:
        lat, lng = float(first["lat"]), float(first["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    rank = first.get("place_rank")
    details = first.get("namedetails")
    names = tuple(str(v) for v in details.values() if v) if isinstance(details, dict) else ()
    return Hit(lat=lat, lng=lng, place_rank=int(rank) if isinstance(rank, (int, float)) else None,
               display_name=str(first.get("display_name") or ""), names=names)


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle (haversine) distance in km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def accept(hit: Hit | None, centre: CityCentre) -> bool:
    """Whether a hit plausibly locates a venue in the city: precise enough
    (not the city / a district / a postcode area) and near the centre."""
    if hit is None:
        return False
    if hit.place_rank is not None and hit.place_rank < MIN_PLACE_RANK:
        return False
    d = distance_km(hit.lat, hit.lng, centre.lat, centre.lng)
    if hit.place_rank is None and d < _CENTRE_EPS_KM:
        return False  # unknown precision, sitting on the centre: the city itself
    return d <= MAX_DISTANCE_KM


# --- I/O --------------------------------------------------------------------

Getter = Callable[[str, dict], object]  # (url, params) -> parsed JSON


class Nominatim:
    """Rate-limited Nominatim search (≤ 1 request / MIN_INTERVAL_S)."""

    def __init__(self, get: Getter | None = None, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._client: httpx.Client | None = None
        self._get = get or self._http_get
        self._sleep, self._clock = sleep, clock
        self._last: float | None = None
        self.requests = 0

    def _http_get(self, url: str, params: dict) -> object:
        if self._client is None:
            self._client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20)
        for attempt in range(RETRIES_429 + 1):
            r = self._client.get(url, params=params)
            if r.status_code != 429 or attempt == RETRIES_429:
                break
            wait = max(_retry_after(r.headers.get("Retry-After")),
                       BACKOFF_429_S * 2 ** attempt)
            logger.warning("geocode: throttled by Nominatim (429); waiting %.0fs", wait)
            self._sleep(wait)
        r.raise_for_status()
        return r.json()

    def search(self, query: Query, country: str) -> Hit | None:
        if self._last is not None:
            wait = MIN_INTERVAL_S - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        try:
            payload = self._get(NOMINATIM_URL, {
                **({"q": query} if isinstance(query, str) else query),
                "format": "jsonv2", "limit": 1, "countrycodes": country,
                # all of the place's names (local, English, ...): name_matches
                # compares them against our venue names (e.g. Latin-script
                # names of Yerevan venues whose local name is Armenian)
                "namedetails": 1})
        finally:
            self._last = self._clock()
            self.requests += 1
        return parse_response(payload)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


def _retry_after(header: str | None) -> float:
    try:
        return max(1.0, float(header)) if header else BACKOFF_429_S
    except ValueError:
        return BACKOFF_429_S


def locate(nominatim: Nominatim, name: str, address: str | None, city_name: str,
           centre: CityCentre) -> Hit | None:
    """The venue's position, or None (see the module docstring for the order)."""
    street: Hit | None = None
    for q in address_queries(address, city_name):
        hit = nominatim.search(q, centre.country)
        if accept(hit, centre):
            if hit.place_rank is None or hit.place_rank >= PRECISE_RANK:
                return hit
            street = street or hit
        elif hit is not None:
            logger.info("geocode: rejected %r -> %s (rank %s)", q, hit.display_name,
                        hit.place_rank)
    q = name_query(name, city_name)
    hit = nominatim.search(q, centre.country)
    if accept(hit, centre) and name_matches(name, hit) and (
            street is None or _agrees_with_street(hit, street)):
        return hit
    if hit is not None:
        logger.info("geocode: rejected %r -> %s (rank %s)", q, hit.display_name, hit.place_rank)
    return street


def _agrees_with_street(poi: Hit, street: Hit) -> bool:
    """A name-matched POI confirms a street-level address hit when it lies on
    that street (the street's name appears in its address — the street hit
    may be a far-off segment, or a same-named street in a neighbouring town)
    or close to it."""
    street_name = street.display_name.split(",")[0]
    on_street = bool(_words(street_name)) and _words(street_name) <= _words(poi.display_name)
    return on_street or distance_km(poi.lat, poi.lng, street.lat, street.lng) <= NAME_NEAR_STREET_KM


def explicit_coordinate_slugs() -> set[str]:
    """Slugs of code-defined venues carrying explicit lat/lng (never geocoded)."""
    from cartelera.scrapers import REGISTRY, load_all
    load_all()
    return {v.slug for _s, src in REGISTRY.values() for v in src.venues if v.lat is not None}


def geocode_venues(
    session: Session, *, city_slug: str | None = None, force: bool = False,
    max_venues: int | None = None, nominatim: Nominatim | None = None,
    explicit: set[str] | None = None, now: Callable[[], dt.datetime] | None = None,
    progress: Callable[[str], None] | None = None,
) -> GeocodeReport:
    """Geocode venues lacking a lookup (`geocoded_at IS NULL`; with `force`,
    every venue), optionally in one city, at most `max_venues` of them.
    Venues with explicit coordinates in code are never touched. Commits per
    venue, so an interrupted pass keeps its progress. HTTP errors propagate
    (the venue stays pending)."""
    explicit = explicit_coordinate_slugs() if explicit is None else explicit
    now = now or (lambda: dt.datetime.now(dt.timezone.utc))
    q = select(Venue, City).join(City, City.id == Venue.city_id).order_by(City.slug, Venue.slug)
    if city_slug:
        q = q.where(City.slug == city_slug)
    if not force:
        q = q.where(Venue.geocoded_at.is_(None))
    pending = [(v, c) for v, c in session.execute(q).all() if v.slug not in explicit]

    report = GeocodeReport()
    own = nominatim is None
    nominatim = nominatim or Nominatim()
    try:
        for i, (venue, city) in enumerate(pending):
            if max_venues is not None and i >= max_venues:
                report.skipped = len(pending) - i
                break
            centre = CITY_CENTRES.get(city.slug)
            if centre is None:
                logger.warning("geocode: no CITY_CENTRES entry for %r; skipping %s",
                               city.slug, venue.slug)
                continue
            hit = locate(nominatim, venue.name, venue.address, city.name, centre)
            if hit:
                venue.lat, venue.lng = hit.lat, hit.lng
                report.hits.append((city.slug, venue.slug, hit))
                line = f"[hit]  {city.slug}/{venue.slug}: {hit.lat:.5f},{hit.lng:.5f}  " \
                       f"{hit.display_name[:90]}"
            else:
                venue.lat = venue.lng = None
                report.misses.append((city.slug, venue.slug, venue.name))
                line = f"[miss] {city.slug}/{venue.slug}: {venue.name}"
            if progress:
                progress(line)
            venue.geocoded_at = now()
            session.commit()
    finally:
        if own:
            nominatim.close()
    return report


def print_summary(report: GeocodeReport) -> None:
    tail = f", {report.skipped} left for a later pass" if report.skipped else ""
    print(f"geocoded: {len(report.hits)} hits, {len(report.misses)} misses{tail}")


def main(session: Session, args: list[str]) -> int:
    """`cartelera geocode [--city <slug>] [--force]`."""
    city: str | None = None
    force = False
    it = iter(args)
    for a in it:
        if a == "--force":
            force = True
        elif a == "--city":
            city = next(it, None)
            if not city:
                print("usage: cartelera geocode [--city <slug>] [--force]")
                return 1
        else:
            print(f"unknown argument {a!r}; usage: cartelera geocode [--city <slug>] [--force]")
            return 1
    if city and city not in CITY_CENTRES:
        print(f"unknown city {city!r}; known: {sorted(CITY_CENTRES)}")
        return 1
    print_summary(geocode_venues(session, city_slug=city, force=force,
                                 progress=lambda line: print(line, flush=True)))
    return 0
