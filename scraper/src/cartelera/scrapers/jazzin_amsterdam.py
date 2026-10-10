from __future__ import annotations
import datetime as dt
import logging
import re

import httpx

from cartelera.scrapers import register_source
from cartelera.types import (
    ScrapedEvent,
    VenueDefinition,
    ListMembership,
    SourceDefinition,
)

# jazzin.amsterdam — a curated Amsterdam jazz calendar (~640 upcoming gigs
# across ~60 venues) with a public JSON API. MULTI-VENUE source: the VENUES
# table below is the editorial whitelist and the name-normalization map (see
# jazzin_amsterdam_SOURCE.md). The API returns at most PAGE_SIZE events per
# call; `offset` pages (its `page` param is ignored).
API_URL = "https://jazzin.amsterdam/api"
API_PARAMS = {"calendar": "jazzAmsterdam", "archive": "false"}
PAGE_SIZE = 600
MAX_PAGES = 10  # safety stop against a misbehaving offset
SOURCE_SLUG = "jazzin-amsterdam"
CITY_SLUG = "amsterdam"
FALLBACK_URL = "https://jazzin.amsterdam/"

logger = logging.getLogger(__name__)

# (venue slug, display name, address, jazzin venue-name aliases). jazzin's
# `venue` field is free text typed per source, so one venue arrives under
# several spellings ("ZOJazz Stage", "ZOjazz Stage", "ZOJazzstage "); aliases
# are matched after _venue_key normalization (case/whitespace-insensitive).
# Addresses are jazzin's, cleaned up; the few it gives only as "Amsterdam" are
# filled in by hand.
VENUES: list[tuple[str, str, str, list[str]]] = [
    ("bimhuis", "Bimhuis", "Piet Heinkade 3, 1019 BR Amsterdam", ["Bimhuis"]),
    ("muziekgebouw", "Muziekgebouw aan 't IJ", "Piet Heinkade 1, 1019 BR Amsterdam", ["Muziekgebouw"]),
    ("cafe-de-pianist", "Café de Pianist", "Groen van Prinstererstraat 41, 1051 EH Amsterdam", ["Café de Pianist"]),
    # "Concertzaal" is the ZOJazz hall in the same building (Bijlmerplein 888).
    ("zojazz-stage", "ZOJazz Stage", "Bijlmerplein 888, 1102 MG Amsterdam-Zuidoost",
     ["ZOJazz Stage", "ZOJazzstage", "Concertzaal"]),
    ("cafe-de-engelbewaarder", "Café de Engelbewaarder", "Kloveniersburgwal 59HS, 1011 JZ Amsterdam",
     ["Café de Engelbewaarder"]),
    ("carre", "Koninklijk Theater Carré", "Amstel 115-125, 1018 EM Amsterdam", ["Carré"]),
    ("contra", "Contra", "Oudezijds Achterburgwal 235, 1012 DL Amsterdam", ["Contra"]),
    ("concertgebouw", "Het Concertgebouw", "Concertgebouwplein 10, 1071 LN Amsterdam", ["Het Concertgebouw"]),
    ("zaal-100", "Zaal 100", "De Wittenstraat 100, 1052 BA Amsterdam", ["Zaal 100"]),
    ("kompaszaal", "Kompaszaal", "KNSM-Laan 311, 1019 LE Amsterdam", ["Kompaszaal"]),
    ("splendor", "Splendor", "Nieuwe Uilenburgerstraat 116, 1011 LX Amsterdam", ["Splendor"]),
    ("melkweg", "Melkweg", "Lijnbaansgracht 234A, 1017 PH Amsterdam", ["Melkweg"]),
    ("cafe-czaar", "Café Czaar", "Czaar Peterstraat 281, 1018 PL Amsterdam", ["Café Czaar"]),
    ("theater-mascini", "Theater Mascini", "Zeedijk 24a, 1012 AZ Amsterdam", ["Theater Mascini"]),
    ("cafe-parisius", "Café Parisius", "Borneostraat 112, Amsterdam", ["Café Parisius"]),
    ("de-roode-bioscoop", "De Roode Bioscoop", "Haarlemmerplein 7, 1013 HP Amsterdam", ["De Roode Bioscoop"]),
    ("de-roode-remise", "De Roode Remise", "Haarlemmerplein 11, 1013 HP Amsterdam", ["De Roode Remise"]),
    ("theater-de-dillewijn", "Theater De Dillewijn (Ankeveen)", "Stichts End 57, 1244 PL Ankeveen",
     ["Theater De Dillewijn (Ankeveen)"]),
    ("de-nieuwe-anita", "De Nieuwe Anita", "Frederik Hendrikstraat 111, 1052 HN Amsterdam", ["De Nieuwe Anita"]),
    ("tolhuistuin", "Tolhuistuin", "IJpromenade 2, 1031 KT Amsterdam", ["Tolhuistuin"]),
    ("occii", "OCCII", "Amstelveenseweg 134, 1075 XL Amsterdam", ["OCCII"]),
    ("plofhuis7", "Plofhuis7 (Weesp)", "Uitermeer 3, 1381 HP Weesp", ["Plofhuis7 (Weesp)"]),
    ("crea", "CREA", "Nieuwe Achtergracht 170, 1018 WV Amsterdam", ["CREA"]),
    ("walhalla", "Walhalla Brouwerij & Proeflokaal", "Asterweg 2, 1031 HN Amsterdam",
     ["Walhalla Brouwerij & Proeflokaal"]),
    ("de-khl", "De KHL", "Oostelijke Handelskade 44, 1019 BM Amsterdam", ["De KHL"]),
    ("de-duif", "De Duif", "Prinsengracht 756, 1017 LD Amsterdam", ["De Duif"]),
    ("salon-de-ijzerstaven", "Salon de IJzerstaven", "Bickersgracht 10, 1013 LE Amsterdam", ["Salon de IJzerstaven"]),
    ("cultureel-cafe-bacchus", "Cultureel Café Bacchus (Aalsmeer)", "Gerberastraat 4, 1431 SG Aalsmeer",
     ["Cultureel Café Bacchus"]),
    ("van-puffelen", "Van Puffelen", "Prinsengracht 375, Amsterdam", ["Van Puffelen"]),
    ("paradiso", "Paradiso", "Weteringschans 6-8, 1017 SG Amsterdam", ["Paradiso"]),
    ("elsas-cafe", "Elsa's Café", "Middenweg 73, 1098 AE Amsterdam", ["Elsa's Café"]),
    ("oedipus-brewing", "Oedipus Brewing", "Schaafstraat 21, 1021 KD Amsterdam", ["Oedipus Brewing"]),
    ("societeit-de-kring", "Sociëteit de Kring", "Kleine-Gartmanplantsoen 7-9, 1017 RP Amsterdam",
     ["Sociëteit de Kring"]),
    ("pianola-museum", "Pianola Museum", "Westerstraat 106, 1015 MN Amsterdam", ["Pianola Museum"]),
    ("greene-room", "Greene Room", "Elementenstraat 16, Amsterdam Westpoort", ["Greene Room"]),
    ("laurierstraat-72", "Laurierstraat 72", "Laurierstraat 72, Amsterdam", ["Laurierstraat 72"]),
    ("theater-de-griffioen", "Theater de Griffioen", "De Boelelaan 1111, 1081 HV Amsterdam",
     ["Theater de Griffioen"]),
    ("theater-de-omval", "Theater de Omval (Diemen)", "Ouddiemerlaan 104, 1111 HL Diemen", ["Theater de Omval"]),
    ("de-boule-de-boule", "De Boule De Boule", "Waterlooplein 6A, 1011 PG Amsterdam", ["De Boule De Boule"]),
    ("huis-de-pinto", "Huis de Pinto", "St. Antoniesbreestraat 69, 1011 HB Amsterdam", ["Huis de Pinto"]),
    ("volkshotel", "Volkshotel", "Wibautstraat 150, 1091 GR Amsterdam", ["Volkshotel"]),
    ("ramses-shaffy-huis", "Sociëteit Ramses Shaffy Huis", "Piet Heinkade 231, 1019 HM Amsterdam",
     ["Sociëteit Ramses Shaffy Huis"]),
    ("het-molenpad", "Het Molenpad", "Prinsengracht 653, Amsterdam", ["Het Molenpad"]),
    # The Conservatorium van Amsterdam lists its Blue Dock hall separately.
    ("conservatorium-van-amsterdam", "Conservatorium van Amsterdam", "Oosterdokskade 151, 1011 DL Amsterdam",
     ["CvA", "Amsterdam Blue Dock, CvA"]),
    ("a-beautiful-mess", "A Beautiful Mess", "Oosterdokskade 227, 1011 DL Amsterdam", ["A Beautiful Mess"]),
    ("podium-genieten", "Podium Genieten", "Oranje Vrijstaatplein 2, 1093 NG Amsterdam", ["Podium Genieten"]),
    ("posthoornkerk", "Posthoornkerk", "Haarlemmerstraat 124, 1013 EX Amsterdam", ["Posthoornkerk"]),
    ("breugem-meeting-point", "Breugem Meeting Point", "Nieuwe Hemweg 2, 1013 BG Amsterdam",
     ["Breugem Meeting Point"]),
    ("theater-de-richel", "Theater De Richel", "Nieuwezijds Voorburgwal 282, 1012 RT Amsterdam",
     ["Theater De Richel"]),
    ("oba-javaplein", "OBA Javaplein", "Javaplein 2, 1094 HW Amsterdam", ["OBA Javaplein"]),
    ("t-zonnehuis", "'t Zonnehuis", "Zonneplein 30, 1033 EK Amsterdam", ["'t Zonnehuis"]),
    ("hans-brinker-bar", "Hans Brinker Bar", "Kerkstraat 136, Amsterdam", ["Hans Brinker Bar"]),
    ("jazzcafe-nieuwemeer", "Jazzcafé NieuweMeer (Aalsmeer)", "Stommeerweg 2, Aalsmeer",
     ["Jazzcafé NieuweMeer Aalsmeer"]),
    ("vreugdehof", "Vreugdehof", "De Klencke 111, 1083 HH Amsterdam", ["Vreugdehof, Amsterdam"]),
    ("theater-vrijburcht", "Theater Vrijburcht", "Jan Olphert Vaillantlaan 143, 1086 XZ Amsterdam",
     ["Theater Vrijburcht"]),
    ("meervaart", "Meervaart", "Meer en Vaart 300, 1068 LE Amsterdam", ["Meervaart Theater"]),
    ("a-lab", "A Lab", "Overhoeksplein 2, 1031 KS Amsterdam", ["A Lab"]),
    ("elthetokerk", "Elthetokerk", "Javastraat 118, 1094 HP Amsterdam", ["Elthethokerk", "Elthetokerk"]),
]


def _venue_key(name: str) -> str:
    """Normalize a jazzin venue name for alias matching: case- and
    whitespace-insensitive ("ZOjazz Stage", "ZOJazzstage " → "zojazzstage")."""
    return re.sub(r"\s+", "", name).casefold()


VENUE_BY_KEY: dict[str, str] = {
    _venue_key(alias): slug for slug, _name, _addr, aliases in VENUES for alias in aliases
}


# --- price -----------------------------------------------------------------

# An amount with optional decimals: "12", "12.5", "12,50", "15.00".
_AMOUNT_RE = re.compile(r"\d+(?:[.,]\d+)?")
_FREE = {"free", "gratis", "0", "€0", "€ 0"}
_SOLD_OUT = {"s.o.", "sold out", "uitverkocht"}


def _fmt_amount(x: float) -> str:
    """12.0 → "12", 12.5 → "12,50" (Dutch decimal comma, like "8,50€")."""
    return str(int(x)) if x == int(x) else f"{x:.2f}".replace(".", ",")


def parse_price(raw: str) -> str | None:
    """jazzin price free text → the price convention.

    "" / bare "€" → None; "free" / "0" → "free"; "s.o." → "sold-out"; amounts
    ("€13", "EUR 15.00", "€12.5–€25", "6 / 12.5") → "13€" etc., with the shared
    2× rule: a range only when the high price is at least twice the low, else
    the highest. Text with no amount ("donatie") passes through as-is."""
    text = raw.strip()
    low = text.casefold()
    if not text or text == "€":
        return None
    if low in _FREE:
        return "free"
    if low in _SOLD_OUT:
        return "sold-out"
    amounts = [float(a.replace(",", ".")) for a in _AMOUNT_RE.findall(text)]
    if not amounts:
        return text
    lo, hi = min(amounts), max(amounts)
    if hi <= 0:
        return "free"
    if lo == hi or hi < 2 * lo:
        return f"{_fmt_amount(hi)}€"
    return f"{_fmt_amount(lo)}–{_fmt_amount(hi)}€"


# --- events ----------------------------------------------------------------

def _parse_time(raw: str | None) -> dt.time | None:
    if not raw:
        return None
    try:
        return dt.time.fromisoformat(raw)
    except ValueError:
        return None


def parse_events(items: list[dict]) -> tuple[list[ScrapedEvent], set[str]]:
    """Map the API's event objects to ScrapedEvents. Pure: JSON in, events out.

    Returns the events plus the set of venue names not in VENUES (dropped —
    the whitelist; logged so new venues get added deliberately).

    jazzin repeats some events under several ids (Muziekgebouw lists a concert
    up to 5×), so occurrences are de-duplicated on (venue, date, time, title),
    keeping the lowest id."""
    events: list[ScrapedEvent] = []
    unknown: set[str] = set()
    seen: set[tuple] = set()
    for item in sorted(items, key=lambda i: i.get("id") or 0):
        venue_name = (item.get("venue") or "").strip()
        venue_slug = VENUE_BY_KEY.get(_venue_key(venue_name))
        if venue_slug is None:
            unknown.add(venue_name)
            continue
        title = (item.get("title") or "").strip()
        if not title or not item.get("date"):
            continue
        try:
            start_date = dt.date.fromisoformat(item["date"])
        except ValueError:
            continue
        start_time = _parse_time(item.get("time"))

        key = (venue_slug, start_date, start_time, title.casefold())
        if key in seen:
            continue
        seen.add(key)

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                source_url=(item.get("site") or "").strip() or FALLBACK_URL,
                category_slugs=["jazz"],
                price=parse_price(item.get("price") or ""),
                external_id=str(item["id"]),
                venue_slug=venue_slug,
            )
        )
    return events, unknown


def fetch_items() -> list[dict]:
    """Every upcoming event, paging by offset until a short page."""
    items: list[dict] = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for page in range(MAX_PAGES):
            resp = client.get(API_URL, params={**API_PARAMS, "offset": page * PAGE_SIZE})
            resp.raise_for_status()
            batch = resp.json()
            items.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
    return items


class JazzinAmsterdamScraper:
    def scrape(self) -> list[ScrapedEvent]:
        events, unknown = parse_events(fetch_items())
        if unknown:
            logger.warning(
                "jazzin-amsterdam: dropped events at venues not in VENUES: %s",
                ", ".join(sorted(unknown)),
            )
        return events


register_source(
    scraper=JazzinAmsterdamScraper(),
    source=SourceDefinition(
        slug=SOURCE_SLUG,
        name="jazzin.amsterdam",
        venues=[
            VenueDefinition(
                slug=slug,
                name=name,
                city_slug=CITY_SLUG,
                address=address,
                category_slugs=["jazz"],
                list_memberships=[ListMembership(list_slug="jazz")],
            )
            for slug, name, address, _aliases in VENUES
        ],
    ),
)
