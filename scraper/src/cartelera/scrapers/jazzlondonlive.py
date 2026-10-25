"""jazzlondonlive.com — the hand-compiled London jazz gig guide (multi-venue source).

A WHITELIST source (opt-in, like jazz010 — not opt-out like jazzin.amsterdam):
only the venues in `VENUES` are emitted, matched on jazzlondonlive's exact
venue name. Out-of-London clubs, concert halls, dinner/supper-club shows and
venues owned by another Cartelita source are left out on purpose. See
jazzlondonlive_SOURCE.md for the field map and the per-venue rationale.

The guide is compiled per MONTH: `/events_by_month/YYYY/M` lists the venues
with gigs that month and `/venue/YYYY/MM/{id}` lists one venue's gigs. We read
the current and the next month (next month's index stays empty until the
editor posts it, usually in the last days of the month).
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers import register_source
from cartelera.scrapers.http import CARTELITA_COMPAT_UA
from cartelera.scrapers.price import format_gbp, format_gbp_range, gbp_amounts
from cartelera.types import ListMembership, ScrapedEvent, SourceDefinition, VenueDefinition

logger = logging.getLogger(__name__)

BASE_URL = "https://jazzlondonlive.com"
SOURCE_SLUG = "jazzlondonlive"
TZ = ZoneInfo("Europe/London")
MAX_CONCURRENCY = 3


def _key(name: str) -> str:
    return " ".join(name.split()).casefold()


def _venue(slug: str, name: str, address: str, site_url: str | None) -> VenueDefinition:
    return VenueDefinition(
        slug=slug,
        name=name,
        city_slug="london",
        address=address,
        site_url=site_url,
        category_slugs=["jazz"],
        list_memberships=[ListMembership(list_slug="jazz")],
    )


# (slug, our display name, jazzlondonlive's exact venue name, address, site)
# Addresses are jazzlondonlive's own (/jazz-venues), rewritten street-first.
_WHITELIST: list[tuple[str, str, str, str, str | None]] = [
    ("606-club", "606 Club", "606 Club, Chelsea",
     "90 Lots Road, London SW10 0QD", "https://www.606club.co.uk"),
    ("ronnie-scotts", "Ronnie Scott's", "Ronnie Scott's, Soho",
     "47 Frith Street, London W1D 4HT", "https://www.ronniescotts.co.uk"),
    ("vortex-jazz-club", "Vortex Jazz Club", "Vortex Jazz Club, Dalston",
     "11 Gillett Square, London N16 8AZ", "https://www.vortexjazz.co.uk"),
    ("toulouse-lautrec", "Toulouse Lautrec", "Toulouse Lautrec, Kennington",
     "140 Newington Butts, London SE11 4RN", "https://toulouselautrec.co.uk"),
    ("jamboree-london", "Jamboree", "Jamboree, WC1",
     "6 St Chad's Place, London WC1X 9HH", "https://www.jamboreevenue.co.uk"),
    ("jazz-cafe-posk", "Jazz Cafe POSK", "Jazz Cafe POSK, Hammersmith",
     "238-246 King Street, London W6 0RF", "https://jazzcafeposk.org"),
    ("jazzlive-at-the-crypt", "Jazzlive at the Crypt", "Jazzlive at the Crypt, Camberwell",
     "St Giles Church, Camberwell Church Street, London SE5 8RB", "https://www.jazzlive.co.uk"),
    ("spice-of-life", "Spice of Life", "Spice of Life, Soho",
     "6 Moor Street, London W1D 5NA", "https://www.spiceoflifesoho.com"),
    ("morocco-bound-wandsworth", "Morocco Bound Bookshop (Wandsworth)", "Morocco Bound Bookshop, SW18",
     "Unit 3A, Pilot's Walk, New Acres, London SW18 1UZ", "https://www.moroccobound.co.uk"),
    ("morocco-bound-bermondsey", "Morocco Bound (Bermondsey)", "Morocco Bound, SE1",
     "1A Morocco Street, London SE1 3HB", "https://www.moroccobound.co.uk"),
    ("the-archduke", "The Archduke", "The Archduke, Waterloo",
     "Concert Hall Approach, London SE1 8XU",
     "https://www.blackandbluerestaurants.com/our-restaurants/the-archduke/"),
    ("syp", "sYp", "sYp, EC3", "19 Bevis Marks, London EC3A 7JA", "https://www.sypcity.co.uk"),
    ("fox-and-firkin", "Fox & Firkin", "Fox & Firkin, SE13",
     "316a Lewisham High Street, London SE13 6JZ", "https://www.foxfirkin.com"),
    ("east-side-jazz-club", "East Side Jazz Club", "East Side Jazz Club, Leytonstone",
     "2 Harvey Road, London E11 3DB", "https://www.eastsidejazzclub.co.uk"),
    ("clapham-common-jazz-club", "Clapham Common Jazz Club (Omnibus Theatre)",
     "Clapham Common Jazz Club @ Omnibus Theatre",
     "1 Clapham Common North Side, London SW4 0QW", "https://www.omnibus-clapham.org/jazz-club/"),
    ("bulls-head-barnes", "The Bull's Head, Barnes", "Bull's Head, Barnes",
     "373 Lonsdale Road, London SW13 9PY", "https://www.thebullsheadbarnes.com"),
    ("karamel-club", "Karamel Club", "Karamel Club, Wood Green",
     "4 Coburg Road, London N22 6UJ", "https://collage-arts.org"),
    ("the-woodman-highgate", "The Woodman", "The Woodman, Highgate",
     "414 Archway Road, London N6 5UA", "https://www.the-woodman.com"),
    ("duke-of-hamilton-hampstead", "Duke of Hamilton (Hampstead Jazz Club)", "Duke of Hamilton, Hampstead",
     "23-25 New End, London NW3 1JD", "https://hampsteadjazzclub.com"),
    ("george-iv-chiswick", "George IV", "George IV, Chiswick",
     "185 Chiswick High Road, London W4 2DR", "https://www.georgeiv.co.uk"),
    ("bull-and-gate", "Bull & Gate", "Bull & Gate, Kentish Town",
     "389 Kentish Town Road, London NW5 2TJ", "https://www.bullandgatenw5.co.uk"),
    ("club-langley", "Club Langley (Spike's Place)", "Club Langley, Beckenham",
     "2 Hawksbrook Lane, Beckenham BR3 3SR", "https://www.spikesplace.co.uk"),
    ("oval-tavern-croydon", "Oval Tavern", "Oval Tavern, Croydon",
     "131 Oval Road, Croydon CR0 6BR", "http://theovaltavern.co.uk"),
    ("clocktower-cafe-croydon", "Clocktower Cafe", "Clocktower Cafe, Croydon",
     "Croydon Clocktower, Katharine Street, Croydon", None),
    ("jazz-train-shoreditch", "Jazz Train (Rolling Stock)", "Jazz Train, Shoreditch",
     "48 Kingsland Road, London E2 8DA", "https://jazztrainshoreditch.co.uk"),
    ("the-mildmay-club", "The Mildmay Club", "The Mildmay Club",
     "33-34 Newington Green, London N16 9PR", "https://mildmay.club"),
    ("eltham-jazz-club", "Eltham Jazz Club", "Eltham Jazz Club, SE9",
     "Eltham Warren Golf Club, Bexley Road, London SE9 2PE", None),
    ("ziggys-world-jazz-club", "Ziggy's World Jazz Club", "Ziggy's World Jazz Club, N21",
     "The King's Head, 1 The Green, London N21 1BB", "http://www.ziggysclub.com"),
    ("b3-lounge", "B3 Lounge", "B3 Lounge, N12",
     "762-764 High Road, London N12 9QH", "https://b3lounge.live"),
    ("milford-arms-isleworth", "Milford Arms", "Milford Arms, Isleworth",
     "574 London Road, Isleworth TW7 4EY", "https://themilfordarms.co.uk"),
    ("lauderdale-house", "Lauderdale House", "Lauderdale House, Highgate",
     "Waterlow Park, Highgate Hill, London N6 5HG", "https://www.lauderdalehouse.org.uk"),
    ("the-washington-hampstead", "The Washington", "The Washington, NW3",
     "50 England's Lane, London NW3 4UE", "https://www.thewashingtonhampstead.co.uk"),
    ("clissold-arms", "Clissold Arms", "Clissold Arms N2",
     "109 Fortis Green, London N2 9HR", "http://clissoldarms.co.uk"),
    ("springfield-bowls-club", "Springfield Bowls & Social Club", "Springfield Bowls & Social Club",
     "25-27 Western Gardens, London W5 3RS", "https://www.springfieldactonbowlsclub.co.uk"),
    ("the-turks-head-twickenham", "The Turk's Head", "The Turk's Head, Twickenham",
     "28 Winchester Road, Twickenham TW1 1LF", "https://www.turksheadtwickenham.co.uk"),
    ("the-southgate-club", "The Southgate Club", "The Southgate Club",
     "17 Chase Side, London N14 5BP", "https://southgateclub.com"),
]

VENUES: list[VenueDefinition] = [
    _venue(slug, name, address, site) for slug, name, _jll, address, site in _WHITELIST
]

# jazzlondonlive venue names -> venue slug (exact, case/whitespace-insensitive).
ALIASES: dict[str, str] = {_key(jll): slug for slug, _n, jll, _a, _s in _WHITELIST}

# Venue names deliberately left out (reasons in jazzlondonlive_SOURCE.md).
# Known so they're skipped quietly; any OTHER unknown name is logged as a
# warning so a new venue on the guide gets an editorial look.
EXCLUDED: set[str] = {
    _key(n)
    for n in [
        # owned by another Cartelita source
        "PizzaExpress Jazz Club, Soho", "PizzaExpress Live, Holborn",  # pizzaexpress-live
        "91 Living Room, Brick Lane",  # dice-london
        "Green Note, Camden", "Kings Place, N1", "Wigmore Hall, W1",  # classical batch
        "Cadogan Hall, Chelsea", "EartH Theatre, N16", "Hootananny, Brixton",
        # owner decision (out for now)
        "Blue Note London",
        # concert halls / big rooms / megavenues
        "Bechstein Hall", "Royal Albert Hall, Kensington", "O2 Academy, Islington",
        "Jazz Cafe, Camden",
        # dinner / supper-club shows
        "Boisdale of Belgravia", "Boisdale of Canary Wharf", "Crazy Coqs, Live at Zedel",
        "The Pheasantry, Chelsea", "Googlies Jazz Supper Club, Enfield", "Soul Mama Islington",
        # one-off listings at venues without a jazz programme
        "Cafe Yukari, Kew", "Grand Junction, W2", "Orange Box, SW6", "The Cockpit, NW8",
        "The Courtyard Sun St Hotel, EC2A", "Weston Hall", "World Heart Beat, Embassy Gardens",
        "Sundridge Park Working Mens Club, Bromley",
        # outside Greater London
        "Dawkes Music, Maidenhead", "Guildford Pavilion", "The Guildford Institute",
        "The Stoke, Guildford", "Hidden Rooms, Cambridge", "Marigolds Jazz Club, Harlow",
        "Park Inn Hotel, Southend", "The Jazz Centre UK, Southend-on-Sea",
        "South Hill Park Arts Centre, Bracknell", "Splashpoint Jazz Club Eastbourne",
        "The Bardswell Club, Brentwood", "The Bear Club, Luton", "The Harlington, Fleet",
        "Watermill Jazz Club, Dorking",
    ]
}


def venue_slug_for(name: str) -> str | None:
    return ALIASES.get(_key(name))


def months_to_fetch(today: dt.date) -> list[tuple[int, int]]:
    nxt = (today.year + (today.month == 12), today.month % 12 + 1)
    return [(today.year, today.month), nxt]


def parse_month_index(html: str) -> list[tuple[str, str]]:
    """An /events_by_month/YYYY/M page -> [(venue name, venue page path)]."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[tuple[str, str]] = []
    for a in soup.select("div.article a[href^='/venue/']"):
        title = a.select_one("p.title")
        if title:
            out.append((" ".join(title.get_text(" ", strip=True).split()), a["href"]))
    return out


# "01/10/2026 20:30"
_DATETIME_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})\s+(\d{1,2}):(\d{2})$")
_REAL_URL_RE = re.compile(r"^https?://[^/\s]+\.[^/\s]+")


def parse_price(text: str | None) -> str | None:
    """The guide's free-text price -> the price convention.

    "£18" -> "£18"; "Free", "free", "Free/donations" -> "free"; a slash list
    of tiers ("£13 / 10 / 5", "£20 Advance / 23 Door") -> the highest (the
    others are concession/advance tiers); a dash range ("£9 - 22 advance",
    "£28.68 - 51.42") -> a range under the 2x rule. Text without a £ amount
    ("From 15") -> None."""
    if not text:
        return None
    text = " ".join(text.split())
    low = text.casefold()
    if "sold out" in low:
        return "sold-out"
    if low.startswith("free"):
        return "free"
    # Bare numbers in a "/" or "," tier list share the leading £; a
    # one-digit pence ("£12.5") is padded so it isn't read as £12.
    norm = re.sub(r"([/,]\s*)(?=\d)", r"\1£", text)
    norm = re.sub(r"(\d+\.\d)(?!\d)", r"\g<1>0", norm)
    amounts = gbp_amounts(norm)
    if not amounts:
        return None
    if re.search(r"\d\s*[-–]\s*£?\s*\d", norm):
        return format_gbp_range(min(amounts), max(amounts))
    return format_gbp(max(amounts))


def _row(dt_text: str, price: str, link, note: str) -> dict | None:
    m = _DATETIME_RE.match(dt_text)
    if not m:
        logger.warning("jazzlondonlive: unparseable row %r", dt_text)
        return None
    day, month, year, hh, mm = m.groups()
    try:
        date = dt.date(int(year), int(month), int(day))
        time = dt.time(int(hh), int(mm))
    except ValueError:
        logger.warning("jazzlondonlive: bad date/time %r", dt_text)
        return None
    return {
        "start_date": date,
        "start_time": time,
        "price_text": price.strip(),
        "title": " ".join(link.get_text(" ", strip=True).split()),
        "href": (link.get("href") or "").strip(),
        "note": note,
    }


def _clean(text: str) -> str:
    return " ".join(text.split())


def parse_dates_page(html: str) -> list[dict]:
    """/jazz-dates (the current month, all venues) -> rows with "venue".

    Each row: `span.text-white` = three lines (date+time / venue / price),
    `a` = title + outbound link, `span.text-888B8D` = the editor's note."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for h3 in soup.select("div.entry-content h3"):
        span = h3.select_one("span.text-white")
        link = h3.find("a")
        if not (span and link):
            continue
        lines = [_clean(x) for x in span.get_text("\n").split("\n") if x.strip()]
        if len(lines) < 2:
            logger.warning("jazzlondonlive: unparseable row %r", lines)
            continue
        note_el = h3.select_one("span.text-888B8D")
        row = _row(lines[0], lines[2] if len(lines) > 2 else "", link,
                   _clean(note_el.get_text(" ", strip=True)) if note_el else "")
        if row:
            row["venue"] = lines[1]
            rows.append(row)
    return rows


def parse_venue_page(html: str) -> tuple[str | None, list[dict]]:
    """A /venue/YYYY/MM/{id} page -> (venue name, rows).

    Same rows minus the venue line; here the editor's note is folded into
    the title as a "(note)" suffix (the `p.text-888B8D` stays empty), so
    titles read from these pages can differ from /jazz-dates — which is why
    the occurrence key doesn't use the title (see build_event)."""
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.select_one("h1.entry-title")
    name = _clean(h1.get_text(" ", strip=True)) if h1 else None
    rows: list[dict] = []
    for h3 in soup.select("div.entry-content h3"):
        span = h3.select_one("span.text-white")
        link = h3.find("a")
        if not (span and link):
            continue
        m = re.match(r"^(\S+\s+\S+)\s*(.*)$", _clean(span.get_text(" ", strip=True)))
        if not m:
            continue
        note_el = h3.find_next_sibling()
        note = ""
        if note_el is not None and note_el.name == "p" and "text-888B8D" in (note_el.get("class") or []):
            note = _clean(note_el.get_text(" ", strip=True))
        row = _row(m.group(1), m.group(2), link, note)
        if row:
            rows.append(row)
    return name, rows


def build_event(row: dict, venue_slug: str, venue_page_url: str) -> ScrapedEvent | None:
    if not row["title"]:
        return None
    href = row["href"]
    real = bool(_REAL_URL_RE.match(href))
    note = row["note"]
    # The editor's note is either a short label ("Live Show", "Jam Session")
    # or a sentence about the gig.
    annotations = [note] if note and len(note.split()) <= 3 else []
    description = note if note and not annotations else None
    t = row["start_time"]
    # No per-event id on the guide; the outbound link is often the venue's
    # generic listing page or shared by a residency's nights, and titles
    # differ between /jazz-dates and the venue pages. So the occurrence key
    # is date + time + link (a clash within one venue is resolved by
    # events_from_rows).
    key = f"{row['start_date'].isoformat()}T{t.strftime('%H%M')}"
    return ScrapedEvent(
        title=row["title"],
        start_date=row["start_date"],
        start_time=t,
        start_times=[t],
        source_url=href if real else venue_page_url,
        category_slugs=["jazz"],
        price=parse_price(row["price_text"]),
        description=description,
        external_id=f"{key}@{href}" if real else key,
        annotations=annotations,
        venue_slug=venue_slug,
    )


def select_venues(index: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The month index -> [(venue slug, venue page path)] for whitelisted
    venues; unknown names are logged for review."""
    kept: list[tuple[str, str]] = []
    unknown: list[str] = []
    for name, path in index:
        slug = venue_slug_for(name)
        if slug:
            kept.append((slug, path))
        elif _key(name) not in EXCLUDED:
            unknown.append(name)
    if unknown:
        logger.warning("jazzlondonlive: venues not in the whitelist (review): %s",
                       ", ".join(sorted(set(unknown))))
    return kept


def events_from_rows(rows: list[tuple[str, str, dict]], today: dt.date) -> list[ScrapedEvent]:
    """[(venue slug, venue page url, row)] -> upcoming events, one per
    occurrence. Two different gigs on one key (same venue, date, time and
    link) get the title appended; an exact repeat is dropped."""
    events: list[ScrapedEvent] = []
    seen: dict[tuple[str, str], str] = {}
    for slug, url, row in rows:
        if row["start_date"] < today:
            continue
        ev = build_event(row, slug, url)
        if ev is None:
            continue
        key = (slug, ev.external_id)
        if key in seen:
            if seen[key] == ev.title:
                continue
            ev.external_id = f"{ev.external_id}#{ev.title}"
            key = (slug, ev.external_id)
            if key in seen:
                continue
        seen[key] = ev.title
        events.append(ev)
    return events


def whitelisted_rows(dates_rows: list[dict], index: list[tuple[str, str]]) -> list[tuple[str, str, dict]]:
    """/jazz-dates rows at whitelisted venues, with the venue's page URL
    (from that month's index) as the fallback link."""
    paths = {_key(name): path for name, path in index}
    out: list[tuple[str, str, dict]] = []
    unknown: set[str] = set()
    for row in dates_rows:
        slug = venue_slug_for(row["venue"])
        if slug is None:
            if _key(row["venue"]) not in EXCLUDED:
                unknown.add(row["venue"])
            continue
        path = paths.get(_key(row["venue"]))
        out.append((slug, BASE_URL + path if path else f"{BASE_URL}/jazz-dates", row))
    if unknown:
        logger.warning("jazzlondonlive: venues not in the whitelist (review): %s",
                       ", ".join(sorted(unknown)))
    return out


def rows_from_venue_pages(pages: list[tuple[str, str, str]]) -> list[tuple[str, str, dict]]:
    """[(venue slug, page url, html)] -> rows, checking each page is the
    venue the index said it was."""
    out: list[tuple[str, str, dict]] = []
    for slug, url, html in pages:
        name, rows = parse_venue_page(html)
        if name is not None and venue_slug_for(name) != slug:
            raise RuntimeError(f"jazzlondonlive: {url} is {name!r}, expected venue {slug}")
        out.extend((slug, url, row) for row in rows)
    return out


class JazzLondonLiveScraper:
    def scrape(self) -> list[ScrapedEvent]:
        today = dt.datetime.now(TZ).date()
        headers = {"User-Agent": CARTELITA_COMPAT_UA}
        with httpx.Client(headers=headers, follow_redirects=True, timeout=30) as client:
            def get(url: str) -> str:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.text

            # The current month: every venue on one page.
            dates_rows = parse_dates_page(get(f"{BASE_URL}/jazz-dates"))
            if not dates_rows:
                # The current month always has hundreds of gigs; none means
                # the markup changed.
                raise RuntimeError("jazzlondonlive: /jazz-dates has no rows")
            covered = {(r["start_date"].year, r["start_date"].month) for r in dates_rows}

            rows: list[tuple[str, str, dict]] = []
            targets: list[tuple[str, str]] = []
            for year, month in months_to_fetch(today):
                index = parse_month_index(get(f"{BASE_URL}/events_by_month/{year}/{month}"))
                if (year, month) in covered:
                    month_rows = [r for r in dates_rows
                                  if (r["start_date"].year, r["start_date"].month) == (year, month)]
                    rows.extend(whitelisted_rows(month_rows, index))
                else:
                    # Not on /jazz-dates (next month, once posted): one page
                    # per whitelisted venue.
                    targets.extend(select_venues(index))

            # A failing venue page raises: partial data would read as misses.
            def fetch(target: tuple[str, str]) -> tuple[str, str, str]:
                slug, path = target
                url = BASE_URL + path
                return slug, url, get(url)

            with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
                pages = list(pool.map(fetch, targets))
        rows.extend(rows_from_venue_pages(pages))
        return events_from_rows(rows, today)


register_source(
    scraper=JazzLondonLiveScraper(),
    source=SourceDefinition(slug=SOURCE_SLUG, name="jazzlondonlive", venues=VENUES),
)
