from __future__ import annotations
import datetime as dt
import html as html_module
import re

import httpx
from bs4 import BeautifulSoup, Tag

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# Basílica de Santa Maria del Pi (Gothic church, Barri Gòtic, Barcelona). The
# basilica is a parish, and its public programme lives in a single WordPress
# "Simple Calendar" (simcal) month grid at `/ca/agenda/`. That page server-renders
# every dated event for the current month as one `<li class="simcal-event">` per
# occurrence, each carrying schema.org microdata: an ISO `content` datetime on
# `.simcal-event-start-date` / `-start-time`, the title in
# `span.simcal-event-title[itemprop=name]`, a free-text description (with a "Lloc:"
# location and an optional "Més informació" link to the basilica's own event page),
# and a Google-Calendar "Més detalls" link whose `eid` is a stable per-occurrence id.
# A single request is a complete source for the current month — no detail fetch.
#
# The agenda is mostly the parish LITURGICAL calendar (daily "Missa"); concerts are
# occasional. Cartelera lists cultural events, not religious services, so we keep
# only concert/recital occurrences AT the basilica and drop masses and off-site
# parish events. Church concerts here (choirs, early music, chamber/cobla) map to
# `classical`. See santa_maria_del_pi_SOURCE.md.
AGENDA_URL = "https://basilicadelpi.cat/ca/agenda/"
BASE_URL = "https://basilicadelpi.cat"
VENUE_SLUG = "santa-maria-del-pi"

# Catalan/Spanish free-entry phrases → "free".
_FREE_PHRASES = (
    "entrada lliure",
    "entrada gratuïta",
    "activitat gratuïta",
    "entrada gratuita",
    "entrada libre",
    "gratis",
    "gratuït",
    "gratuita",
)
_SOLD_OUT_PHRASES = ("exhaurit", "exhaurides", "esgotad", "s.o.", "sold out", "completo", "complet")

# A title is a concert/cultural-music event (vs. a Missa or other liturgical/parish
# act) if it mentions any of these. Liturgical acts ("Missa", "Celebració…") are
# excluded; "Concert-conferència" etc. still match on "concert".
_CONCERT_WORDS = re.compile(
    r"\b(concert|recital|cantata|coral|polifònic|polifonic|música|musica|"
    r"orquestr|cobla|cor\b|vespres|gospel|nadales)",
    re.IGNORECASE,
)
# Liturgical / non-cultural acts to exclude even if a description mentions a concert.
_LITURGY_WORDS = re.compile(r"\b(missa|eucaristia|pregària|pregaria|rosari|via crucis)\b", re.IGNORECASE)

# Price in the free-text description, e.g. "Preu: 12€" / "Entrada: 10 €".
_PRICE = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*€")


def _clean(text: str) -> str:
    return html_module.unescape(text).replace("\xa0", " ").replace("­", "").strip()


def _absolutize(url: str) -> str:
    if not url:
        return url
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE_URL + url
    return url


def _normalize_price(text: str | None) -> str | None:
    """Map a free-text description to the price convention (None/free/sold-out/"N€")."""
    if not text:
        return None
    low = text.lower()
    if any(p in low for p in _SOLD_OUT_PHRASES):
        return "sold-out"
    if any(p in low for p in _FREE_PHRASES):
        return "free"
    amounts = _PRICE.findall(text)
    if amounts:
        # Highest public price (skip member/discount tiers implicitly by taking max).
        def _num(a: str) -> float:
            return float(a.replace(".", "").replace(",", "."))

        best = max(amounts, key=_num)
        return f"{best.replace(',', '.').rstrip('0').rstrip('.') if ('.' in best or ',' in best) else best}€"
    return None


def _iso_datetime(li: Tag, selector: str) -> dt.datetime | None:
    el = li.select_one(selector)
    raw = el.get("content") if el else None
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


def _is_concert(title: str, description: str) -> bool:
    """True for cultural music events at the basilica; False for masses/parish acts."""
    if _LITURGY_WORDS.search(title):
        return False
    return bool(_CONCERT_WORDS.search(title))


def parse_agenda(html: str) -> list[ScrapedEvent]:
    """Parse the simcal agenda into one ScrapedEvent per concert occurrence.

    Keeps only concert/recital events (drops the daily Missa and other liturgical or
    off-site parish acts). Each kept `li.simcal-event` yields: title from
    `span.simcal-event-title[itemprop=name]`; start date/time from the schema.org ISO
    `content` on `.simcal-event-start-date`/`-start-time`; end time likewise; price
    parsed from the free-text description if present; source_url preferring the
    basilica "Més informació" page over the Google-Calendar link. The external_id is
    the Google-Calendar `eid` (stable, already per-occurrence); we still qualify a
    missing one with date+time to keep occurrences distinct."""
    soup = BeautifulSoup(html, "html.parser")

    events: list[ScrapedEvent] = []
    seen: set[str] = set()
    for li in soup.select("li.simcal-event"):
        name_el = li.select_one("span.simcal-event-title[itemprop='name']") or li.select_one(
            "span.simcal-event-title"
        )
        title = _clean(name_el.get_text(" ", strip=True)) if name_el else ""
        if not title:
            continue

        desc_el = li.select_one(".simcal-event-description")
        description = _clean(desc_el.get_text(" ", strip=True)) if desc_el else ""

        if not _is_concert(title, description):
            continue

        start_dt = _iso_datetime(li, ".simcal-event-start-date")
        if start_dt is None:
            continue  # no reliable date; skip rather than guess
        start_date = start_dt.date()

        time_el = _iso_datetime(li, ".simcal-event-start-time")
        start_time = time_el.time() if time_el else start_dt.time()
        end_el = _iso_datetime(li, ".simcal-event-end-time")
        end_time = end_el.time() if end_el else None

        # Prefer the basilica's own event page; fall back to the Google-Calendar link.
        basilica_link = None
        gcal_link = None
        for a in li.select("a[href]"):
            href = a.get("href", "").strip()
            if "basilicadelpi" in href and basilica_link is None:
                basilica_link = href
            elif "google.com/calendar" in href and gcal_link is None:
                gcal_link = href
        source_url = _absolutize(basilica_link or gcal_link or AGENDA_URL)

        # external_id: the Google-Calendar eid is stable and already per-occurrence.
        eid = None
        if gcal_link:
            m = re.search(r"[?&]eid=([^&]+)", gcal_link)
            eid = m.group(1) if m else None
        time_part = start_time.strftime("%H%M") if start_time else "0000"
        external_id = eid or f"{start_date.isoformat()}T{time_part}-{abs(hash(title)) % 10**8}"
        if external_id in seen:
            continue
        seen.add(external_id)

        events.append(
            ScrapedEvent(
                title=title,
                start_date=start_date,
                start_time=start_time,
                end_time=end_time,
                source_url=source_url,
                category_slugs=["classical"],
                price=_normalize_price(description),
                external_id=external_id,
            )
        )

    return events


class SantaMariaDelPiScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            html = client.get(AGENDA_URL).text
        return parse_agenda(html)


register(
    scraper=SantaMariaDelPiScraper(),
    venue=VenueDefinition(
        slug=VENUE_SLUG,
        name="Basílica de Santa Maria del Pi",
        city_slug="barcelona",
        address="Plaça del Pi, 7, Ciutat Vella, 08002 Barcelona",
        site_url="https://basilicadelpi.cat",
        category_slugs=["classical"],
        list_memberships=[
            ListMembership(list_slug="classical"),
        ],
    ),
)
