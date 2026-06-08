from __future__ import annotations
import datetime as dt
import html
import json
import re
import ssl
from pathlib import Path
from zoneinfo import ZoneInfo

import certifi
import httpx

from cartelera.scrapers import register
from cartelera.scrapers.price import format_eur_range
from cartelera.types import ScrapedEvent, VenueDefinition, ListMembership

# L'Auditori de Barcelona — home of the OBC (Barcelona Symphony Orchestra) and
# the Banda Municipal de Barcelona (BMB). The public listing
# (/ca/esdeveniment/) is a JS-rendered WordPress shell with NO event cards in
# the raw HTML — they're injected client-side from a WordPress admin-ajax
# endpoint that returns clean JSON. We hit that endpoint directly (no browser).
#
# `output_profile=all` carries per-session data (one session = one real
# occurrence, with its own datetime/price/id), the price text, and the
# programme taxonomy (tax_ecategory_str) we use to categorize. `limit=500`
# returns the whole programme in one request. See auditori_SOURCE.md.
VENUE_SLUG = "auditori"
BASE_URL = "https://www.auditori.cat"
EVENT_URL_PREFIX = f"{BASE_URL}/ca/esdeveniment/"
AJAX_URL = (
    f"{BASE_URL}/wp-admin/admin-ajax.php"
    "?action=get_auditori_events_query"
    "&page=1&limit=500&output_profile=all&from_date=false&hide_in_page=true"
)

TZ = ZoneInfo("Europe/Madrid")

# auditori.cat serves only its leaf certificate — it omits the Sectigo
# intermediate ("Sectigo Public Server Authentication CA OV R36") that signs it.
# curl works because it chases the AIA caIssuers URL to fetch the missing
# intermediate; Python's ssl module does NOT do AIA chasing, so httpx fails with
# CERTIFICATE_VERIFY_FAILED. We bundle that intermediate and add it to a
# certifi-based context so verification still succeeds WITHOUT disabling it.
_INTERMEDIATE_PEM = Path(__file__).parent / "certs" / "auditori_sectigo_intermediate.pem"


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.load_verify_locations(cafile=str(_INTERMEDIATE_PEM))
    return ctx

# Category discriminator: the venue's own programme category (tax_ecategory_str).
# "Jazz & pop" (and any combined label containing it) → jazz; everything else,
# including Simfònica / Cambra / Antiga / Nova Música / Educatiu / Social and
# empty, defaults to classical. (Nova Música = contemporary art music, still
# classical — no new category needed.)
_JAZZ_MARKER = "jazz"

_PRICE_NUM = re.compile(r"(\d+)\s*€")
_FREE_MARKERS = re.compile(
    r"accés\s+lliure|entrada\s+gratu|activitat\s+gratu|gratu[ïi]ta?|entrada\s+libre|free",
    re.IGNORECASE,
)
_SOLDOUT_MARKERS = re.compile(r"\bs\.?\s*o\.?\b|exhaurit|sold\s*out|esgotad", re.IGNORECASE)
_TBD_MARKERS = re.compile(r"a\s+determinar|per\s+determinar|tbd", re.IGNORECASE)


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    out = html.unescape(text).strip()
    return out or None


def _is_truthy(value) -> bool:
    """Venue flags come as '', '0', 0, False, '1', 1, True — treat the obvious
    falsy markers as not-set."""
    if value is None:
        return False
    s = str(value).strip().lower()
    return s not in ("", "0", "false", "no")


def normalize_price(raw: str | None, sold_out: bool = False) -> str | None:
    """Normalize the venue's free-text price to the project convention:
    None (unknown/TBD), 'free', 'sold-out', or a concise display string.
    A numeric range 'De 12 € a 16 €' → a range or highest price (per the 2× rule
    in format_eur_range); a single/from price → highest value, e.g.
    'A partir de 25 €' → '25€'."""
    if sold_out:
        return "sold-out"
    if not raw:
        return None
    text = html.unescape(raw)
    if _TBD_MARKERS.search(text):
        return None
    nums = [int(m.group(1)) for m in _PRICE_NUM.finditer(text)]
    if nums:
        # A genuine range "De X € a Y €" may keep both ends; otherwise (and when
        # the spread is minor) the highest single public price. format_eur_range
        # applies the 2× rule.
        lo, hi = min(nums), max(nums)
        if len(nums) >= 2 and lo != hi and re.search(r"\bde\b.*\ba\b", text, re.IGNORECASE):
            return format_eur_range(lo, hi)
        return f"{hi}€"
    if _SOLDOUT_MARKERS.search(text):
        return "sold-out"
    if _FREE_MARKERS.search(text):
        return "free"
    # Non-numeric, non-free text like "Entrada del Museu" → unknown.
    return None


def _category_for(ecategory: str | None) -> str:
    if ecategory and _JAZZ_MARKER in html.unescape(ecategory).lower():
        return "jazz"
    return "classical"


def _ts_to_local(ts) -> dt.datetime | None:
    try:
        return dt.datetime.fromtimestamp(int(ts), TZ)
    except (TypeError, ValueError):
        return None


def _build_annotations(event: dict) -> list[str]:
    """Granular programme labels — too fine for a top-level category, surfaced
    as free-form annotations. Category slugs must never leak in here."""
    parts: list[str] = []
    for key in ("tax_ecategory_str", "tax_etype_str", "tax_cicles_str"):
        val = _clean(event.get(key))
        if val:
            # Combined labels like "Concerts / Cursos i tallers" split into parts.
            for piece in val.split(" / "):
                piece = piece.strip()
                if piece and piece not in parts:
                    parts.append(piece)
    subtitle = _clean(event.get("subtitle"))
    if subtitle and subtitle not in parts:
        parts.append(subtitle)
    return parts


def parse_agenda(text: str) -> list[ScrapedEvent]:
    """Parse the admin-ajax JSON (a list of event objects) into ScrapedEvents,
    one per session/occurrence. Each session carries its own datetime, price
    and id; the event carries title, category taxonomy, image and url slug."""
    data = json.loads(text)
    events: list[ScrapedEvent] = []
    for event in data:
        wp_post = event.get("wp_post") or {}
        title = _clean(wp_post.get("post_title"))
        post_name = wp_post.get("post_name")
        if not title or not post_name:
            continue
        source_url = f"{EVENT_URL_PREFIX}{post_name}/"

        category = _category_for(event.get("tax_ecategory_str"))
        is_exhibition = (event.get("tax_etype_str") or "").strip() == "Exposicions"
        annotations = _build_annotations(event)
        image_url = _clean(event.get("image_src"))
        description = _clean(event.get("short_description"))
        event_price = event.get("price_text")

        # Exhibitions are date ranges, not timed occurrences: the session
        # timestamp's time-of-day is the museum opening, not an event start.
        end_date = None
        if is_exhibition:
            last = _ts_to_local(event.get("event_date_last"))
            if last:
                end_date = last.date()

        sessions = event.get("sessions") or []
        for session in sessions:
            start = _ts_to_local(session.get("start_datetime"))
            if start is None:
                continue
            sold_out = _is_truthy(session.get("sold_out"))
            price = normalize_price(session.get("price") or event_price, sold_out)

            start_time: dt.time | None = None
            end_time: dt.time | None = None
            ev_end_date = end_date
            if is_exhibition:
                # range exhibition: keep dates, drop the spurious time
                if ev_end_date and ev_end_date <= start.date():
                    ev_end_date = None
            else:
                start_time = start.time()
                end = _ts_to_local(session.get("end_datetime"))
                if end and end.date() == start.date() and end.time() != start.time():
                    end_time = end.time()

            external_id = session.get("ID")
            if external_id is None:
                continue

            events.append(
                ScrapedEvent(
                    title=title,
                    start_date=start.date(),
                    start_time=start_time,
                    end_date=ev_end_date,
                    end_time=end_time,
                    source_url=source_url,
                    category_slugs=[category],
                    price=price,
                    description=description,
                    image_url=image_url,
                    external_id=f"auditori-session-{external_id}",
                    annotations=annotations,
                )
            )
    return events


class AuditoriScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        text = httpx.get(AJAX_URL, follow_redirects=True, timeout=60, verify=_ssl_context()).text
        return parse_agenda(text)


register(
    scraper=AuditoriScraper(),
    venue=VenueDefinition(
        slug="auditori",
        name="L'Auditori",
        city_slug="barcelona",
        address="C/ de Lepant, 150, 08013 Barcelona",
        site_url="https://www.auditori.cat",
        category_slugs=["classical", "jazz"],
        list_memberships=[
            ListMembership(list_slug="classical", whitelist_category_slug="classical"),
            ListMembership(list_slug="jazz", whitelist_category_slug="jazz"),
        ],
    ),
)
