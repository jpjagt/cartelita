from __future__ import annotations

import datetime as dt
import re
import subprocess
import tempfile
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from PIL import Image

from cartelera.scrapers import register
from cartelera.types import ScrapedEvent

# Casa Figari (Gràcia, Barcelona) is a Squarespace site that publishes its
# weekly agenda exclusively as a single image (figari+2026+feed.png / WebP).
# There is no structured HTML event list, no JSON-LD, and no calendar API.
# The image shows the current week only, Tuesday–Saturday, 2 events per night
# (an evening live act + a late DJ/vinyl session).
#
# Scraping flow:
#   1. Fetch https://www.casafigari.com/inicio HTML
#   2. Extract the schedule image URL from Section 1 (the "Esta semana" banner)
#   3. Download the image (WebP or PNG)
#   4. Run Tesseract OCR with TSV output for bounding-box layout reconstruction
#   5. Reconstruct two-column layout (left=date/time/price, right=artist/desc)
#   6. Parse events from the reconstructed rows
#
# The scraper produces events only for the current week — typically 10 events.

AGENDA_HTML_URL = "https://www.casafigari.com/inicio"
BASE_URL = "https://www.casafigari.com"
VENUE_SLUG = "casa-figari"

# x-coordinate threshold separating the left (date/time/price) column
# from the right (artist/description) column in the schedule image.
LEFT_RIGHT_SPLIT = 380

# Category discriminator: events described as "Strictly Vinyl Discotheque",
# "DJ …", "Listening session", "Vinyl sharing experience", or "TBC DJ SET"
# are club/DJ nights → "club". All other events are jazz concerts → "jazz".
CLUB_KEYWORDS = re.compile(
    r"strictly vinyl|discoth|dj \w|tbc dj|listening session|vinyl sharing|open decks",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# OCR helpers
# ---------------------------------------------------------------------------

def _ocr_image_to_tsv(image_bytes: bytes) -> str:
    """Convert image bytes to Tesseract TSV output (bounding-box per word)."""
    # Tesseract on macOS has issues with /tmp paths under some sandbox
    # configurations; use a persistent cache directory in the user's home.
    cache_dir = Path.home() / ".cache" / "cartelera"
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_dir / "casa_figari_ocr.png"

    # PIL can open WebP and write PNG that Tesseract reliably reads.
    from io import BytesIO
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.save(str(tmp_path), "PNG")

    result = subprocess.run(
        ["tesseract", str(tmp_path), "stdout", "tsv"],
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Tesseract failed (rc={result.returncode}): "
            f"{result.stderr.decode('utf-8', errors='replace')[:500]}"
        )
    return result.stdout.decode("utf-8")


def _tsv_to_rows(tsv: str) -> list[dict]:
    """Parse Tesseract TSV into word-level bounding-box dicts."""
    lines = tsv.strip().split("\n")
    words = []
    for row in lines[1:]:  # skip header
        parts = row.split("\t")
        if len(parts) < 12:
            continue
        if int(parts[0]) != 5:  # level 5 = word
            continue
        conf = float(parts[10])
        text = parts[11].strip()
        if conf <= 0 or not text:
            continue
        words.append(
            {
                "left": int(parts[6]),
                "top": int(parts[7]),
                "text": text,
            }
        )
    return words


def _reconstruct_layout(words: list[dict]) -> list[tuple[str, str]]:
    """Group words by y-band into (left_col_text, right_col_text) rows."""
    # Group by quantised y (20px bands)
    bands: dict[int, list[dict]] = {}
    for w in words:
        key = w["top"] // 20
        bands.setdefault(key, []).append(w)

    rows = []
    for key in sorted(bands):
        band_words = sorted(bands[key], key=lambda w: w["left"])
        left_words = [w["text"] for w in band_words if w["left"] < LEFT_RIGHT_SPLIT]
        right_words = [w["text"] for w in band_words if w["left"] >= LEFT_RIGHT_SPLIT]
        rows.append((" ".join(left_words), " ".join(right_words)))
    return rows


# ---------------------------------------------------------------------------
# Time / date parsing helpers
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"(\d{2})/(\d{2})")
# Matches: "20:30H", "20:30", "23H", "& 22H", "22:00H"
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(?:[Hh])?|(\d{1,2})[Hh]")
_PRICE_RE = re.compile(r"(\d+€|entrada libre)", re.IGNORECASE)
# Matches lines that START with a time token (with optional & prefix).
# Requires H suffix OR colon-minutes to distinguish from price lines like "10€".
_TIME_LEAD_RE = re.compile(r"^(?:&\s+)?\d{1,2}(?::\d{2}[Hh]?|[Hh])\b")


def _parse_time(raw: str) -> dt.time | None:
    """Extract the primary (first) time from a raw string like '20:30H', '23H', '& 22H'.

    Handles both HH:MM and HHH formats, with or without trailing 'H'.
    """
    # Strip & prefix (continuation time marker)
    raw = re.sub(r"^&\s*", "", raw.strip())
    # Try HH:MM format first (e.g. "20:30", "20:30H")
    m = re.search(r"(\d{1,2}):(\d{2})", raw)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return dt.time(hour, minute)
    # Try HH or HHH format (e.g. "23H", "22H")
    m = re.search(r"(\d{1,2})[Hh]", raw)
    if m:
        hour = int(m.group(1))
        if 0 <= hour <= 23:
            return dt.time(hour, 0)
    return None


def _extract_price(left_text: str) -> str | None:
    m = _PRICE_RE.search(left_text)
    if not m:
        return None
    raw = m.group(1).strip()
    if "€" in raw:
        return raw
    # "entrada libre" or similar → normalize to canonical keyword
    return "free"


def _current_year() -> int:
    return dt.date.today().year


def _parse_date(day: str, month: str) -> dt.date:
    year = _current_year()
    d = dt.date(year, int(month), int(day))
    # If the date is more than 90 days in the past, assume next year
    # (handles scraping near year-end)
    if (dt.date.today() - d).days > 90:
        d = dt.date(year + 1, int(month), int(day))
    return d


# ---------------------------------------------------------------------------
# Main parse function
# ---------------------------------------------------------------------------

def parse_schedule(image_bytes: bytes) -> list[ScrapedEvent]:
    """Parse the weekly Casa Figari schedule image into ScrapedEvents.

    Uses Tesseract OCR with bounding-box layout reconstruction to separate
    the left column (date/time/price) from the right column (artist/desc).
    """
    tsv = _ocr_image_to_tsv(image_bytes)
    words = _tsv_to_rows(tsv)
    rows = _reconstruct_layout(words)

    events: list[ScrapedEvent] = []
    current_date: dt.date | None = None

    # We accumulate "events" as we walk the rows.
    # State for the current event being built:
    pending: dict | None = None

    def _flush(ev: dict | None) -> None:
        if ev is None:
            return
        if not ev.get("title") or ev.get("start_time") is None or ev.get("start_date") is None:
            return
        desc_text = ev.get("desc", "")
        is_club = bool(CLUB_KEYWORDS.search(ev["title"] + " " + desc_text))
        category = "club" if is_club else "jazz"
        # Annotations: genre/description text (not empty, not just "Jam Session"
        # or "Listening session" as they're too generic — but keep them)
        annotations = [desc_text] if desc_text else []

        events.append(
            ScrapedEvent(
                title=ev["title"],
                start_date=ev["start_date"],
                start_time=ev["start_time"],
                source_url=BASE_URL,
                category_slugs=[category],
                price=ev.get("price"),
                annotations=annotations,
                external_id=f"{ev['start_date'].isoformat()}_{ev['start_time'].strftime('%H%M')}",
            )
        )

    for left, right in rows:
        left = left.strip()
        right = right.strip()

        # Skip CASAFIGARI footer
        if "CASAFIGARI" in left.upper() and not right:
            continue

        # Detect date in left column
        date_m = _DATE_RE.match(left)
        if date_m:
            # Flush previous pending event first
            _flush(pending)
            pending = None

            current_date = _parse_date(date_m.group(1), date_m.group(2))

            # The rest of left after the date may contain a time
            after_date = left[date_m.end():].strip()
            time_val = _parse_time(after_date) if after_date else None

            # Start a new pending event for show 1 of this day
            pending = {
                "start_date": current_date,
                "start_time": time_val,
                "title": right,
                "desc": "",
                "price": None,
            }
            continue

        # Detect a time-only row (start of a 2nd show on same day, or price row)
        if _TIME_LEAD_RE.match(left):
            # First check: is this a & continuation of an existing time (like "& 22H")?
            is_continuation = left.startswith("&")
            if is_continuation:
                # Ignore — the primary time was already captured; description goes to right
                if pending and right:
                    if pending["desc"]:
                        pending["desc"] += " " + right
                    else:
                        pending["desc"] = right
                continue

            # Otherwise: this is the start of a new event (second show of the night)
            _flush(pending)
            pending = None

            time_val = _parse_time(left)
            if current_date and time_val:
                pending = {
                    "start_date": current_date,
                    "start_time": time_val,
                    "title": right,
                    "desc": "",
                    "price": None,
                }
            continue

        # Detect price row
        price_val = _extract_price(left) if left else None
        if price_val is not None:
            if pending:
                pending["price"] = price_val
                # Right column on a price row is often description continuation
                rest_right = right
                if pending["desc"]:
                    pending["desc"] += " " + rest_right if rest_right else ""
                else:
                    pending["desc"] = rest_right
            continue

        # Pure description / title-continuation row
        if pending and right:
            if not pending["title"]:
                # Title arrived on a separate row (OCR split title from time row)
                pending["title"] = right
            elif pending["desc"]:
                pending["desc"] += " " + right
            else:
                pending["desc"] = right
        if pending and left and not right:
            # Left col text on a non-date/non-time/non-price row: edge case
            if pending["desc"]:
                pending["desc"] += " " + left
            else:
                pending["desc"] = left

    _flush(pending)
    return events


# ---------------------------------------------------------------------------
# HTML-level scraping: extract the schedule image URL from the Inicio page
# ---------------------------------------------------------------------------

def _extract_schedule_image_url(html: str) -> str | None:
    """Find the weekly schedule image URL in the /inicio page HTML.

    The schedule image is in section[1] (the 'Esta semana' section), the only
    img whose filename contains 'figari' or 'feed'.
    """
    soup = BeautifulSoup(html, "html.parser")
    sections = soup.find_all("section")
    if len(sections) < 2:
        return None
    # Search all sections for an img with 'figari' or 'feed' in the src
    for section in sections[:4]:
        for img in section.find_all("img"):
            src = img.get("src", "")
            if "figari" in src.lower() or "feed" in src.lower():
                return src
    # Fallback: first img in section[1]
    if len(sections) >= 2:
        img = sections[1].find("img")
        if img:
            return img.get("src", "")
    return None


def parse_agenda_html(html: str) -> str | None:
    """Return the schedule image URL from the agenda page HTML."""
    return _extract_schedule_image_url(html)


# ---------------------------------------------------------------------------
# Scraper class
# ---------------------------------------------------------------------------

class CasaFigariScraper:
    venue_slug = VENUE_SLUG

    def scrape(self) -> list[ScrapedEvent]:
        html = httpx.get(AGENDA_HTML_URL, follow_redirects=True, timeout=30).text
        image_url = _extract_schedule_image_url(html)
        if not image_url:
            raise RuntimeError(
                "Could not find schedule image URL in Casa Figari agenda page"
            )
        image_bytes = httpx.get(image_url, follow_redirects=True, timeout=30).content
        return parse_schedule(image_bytes)


register(CasaFigariScraper())
