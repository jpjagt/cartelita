"""Shared helpers for Utrecht theatre sites built by cre8ion (with Ticketmatic
ticketing): Stadsschouwburg Utrecht, Theater Kikker, Podium Hoge Woerd and the
Nuxt front-end of Theater Utrecht.

Not a scraper module (the leading underscore keeps `load_all()` from importing
it as one). Each venue keeps its own thin module: the three sites live on
different origins and use different templates — SSBU a paged `ul.events-list`,
Kikker and Hoge Woerd a `div.event.desktop` card list — so what is shared is the
Dutch date/price vocabulary and the polite detail-page fetcher. See
`cre8ion_SOURCE.md`.
"""

from __future__ import annotations

import copy
import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup

from cartelera.scrapers.price import format_eur_range

# Honest, stable identification (docs/nl-cities-plan.md), with a browser token
# because cre8ion sites serve the same HTML either way.
USER_AGENT = (
    "Mozilla/5.0 (compatible; Cartelita (+https://cartelita.july.dev)) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)
# Detail pages are fetched with at most this many requests in flight.
MAX_CONCURRENCY = 3

MONTHS = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "okt": 10, "nov": 11, "dec": 12,
}
WEEKDAYS = {"ma": 0, "di": 1, "wo": 2, "do": 3, "vr": 4, "za": 5, "zo": 6}

_DATE = re.compile(
    r"(?:(?P<wd>ma|di|wo|do|vr|za|zo)\w*\.?\s+)?(?P<day>\d{1,2})\s+(?P<month>[a-z]+)\.?"
    r"(?:\s+(?P<year>\d{4}))?",
    re.IGNORECASE,
)
_TIME = re.compile(r"(?<!\d)(\d{1,2})[:.](\d{2})(?!\d)")  # "20:00u" too
_AMOUNT = re.compile(r"€\s*(\d+(?:[.,]\d{1,2})?)(?:\s*,-)?|(\d+(?:[.,]\d{1,2})?)\s*(?:€|euro\b)")


def client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=30,
    )


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def parse_date(text: str, today: dt.date) -> dt.date | None:
    """A Dutch list date: "wo 14 okt 2026", "wo 14 oktober", "do 15 oktober".

    Without a year (Kikker, Hoge Woerd) the weekday picks the year: of the
    candidate years around `today`, the one where that day falls on the stated
    weekday, nearest to today. Without a weekday either, the date is taken to
    lie at most ~2 months in the past."""
    m = _DATE.search(clean(text))
    if not m:
        return None
    month = MONTHS.get(m.group("month").lower())
    if not month:
        return None
    day = int(m.group("day"))
    if m.group("year"):
        try:
            return dt.date(int(m.group("year")), month, day)
        except ValueError:
            return None
    candidates: list[dt.date] = []
    for year in (today.year - 1, today.year, today.year + 1, today.year + 2):
        try:
            candidates.append(dt.date(year, month, day))
        except ValueError:
            continue
    wd = m.group("wd")
    if wd:
        matching = [c for c in candidates if c.weekday() == WEEKDAYS[wd.lower()[:2]]]
        if matching:
            return min(matching, key=lambda c: abs((c - today).days))
    future = [c for c in candidates if c >= today - dt.timedelta(days=60)]
    return min(future) if future else None


def parse_time(text: str | None) -> dt.time | None:
    """"20:00u" / "20:00" → 20:00. Midnight is the CMS's "no time" sentinel."""
    m = _TIME.search(text or "")
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    if not (0 <= hh < 24 and 0 <= mm < 60) or (hh, mm) == (0, 0):
        return None
    return dt.time(hh, mm)


def amounts(text: str) -> list[Decimal]:
    """Every euro amount in `text` ("€ 25,00", "€10", "€5,-", "12 euro")."""
    out = []
    for a, b in _AMOUNT.findall(text or ""):
        raw = (a or b).replace(",", ".")
        try:
            out.append(Decimal(raw))
        except ArithmeticError:
            continue
    return out


def format_amount(value: Decimal) -> str:
    """12.50 → "12,50€"; 25.00 → "25€"."""
    if value == value.to_integral():
        return f"{int(value)}€"
    return f"{value:.2f}".replace(".", ",") + "€"


def format_tiers(values: list[Decimal]) -> str | None:
    """Seat-rank tiers (all public prices) → one display price on the 2× rule:
    a "lo–hi€" range only when hi >= 2×lo, else the highest. Zero → "free"."""
    if not values:
        return None
    lo, hi = min(values), max(values)
    if hi <= 0:
        return "free"
    if lo == lo.to_integral() and hi == hi.to_integral():
        return format_eur_range(int(lo), int(hi))
    if lo > 0 and hi >= 2 * lo:
        return f"{format_amount(lo)[:-1]}–{format_amount(hi)}"
    return format_amount(hi)


def highest(values: list[Decimal]) -> str | None:
    """A main price among discount tiers ("Van € 10,50 tot € 21,00", where the
    low end is the U-pas 50% discount) → the highest, "free" when it is 0."""
    if not values:
        return None
    top = max(values)
    return "free" if top <= 0 else format_amount(top)


@dataclass
class TicketRow:
    """One date on a Kikker / Hoge Woerd programme detail page."""
    date: dt.date
    time: dt.time | None
    location: str | None
    price: str | None
    # Per-date labels under the date ("Try-out", "met nagesprek", "Verhuur",
    # "Verplaatst", "op locatie").
    labels: list[str] = field(default_factory=list)

    def has_label(self, *names: str) -> bool:
        low = {lab.lower() for lab in self.labels}
        return any(n.lower() in low for n in names)


def _row_value(el) -> str:
    """A ticket-row cell's text without its `<b>Datum</b>`-style label and
    `.label` badges."""
    if el is None:
        return ""
    el = copy.copy(el)
    for b in el.select("b, .label"):
        b.decompose()
    return clean(el.get_text(" "))


def row_price(text: str) -> str | None:
    """A Kikker / Hoge Woerd price cell → display price. "Van € 10,50 tot
    € 21,00" spans the U-pas 50% discount and the full price → the highest."""
    low = text.lower()
    found = amounts(text)
    if found:
        return highest(found)
    if "gratis" in low or "vrije toegang" in low or "free" in low:
        return "free"
    return None


def parse_ticket_rows(html: str, today: dt.date) -> list[TicketRow]:
    """The `.ticket-row.desktop` blocks of a Kikker / Hoge Woerd detail page
    (date, time, hall — the `.genre` cell holds the location — and price)."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[TicketRow] = []
    for row in soup.select(".ticket-row.desktop"):
        date = parse_date(_row_value(row.select_one(".date")), today)
        if not date:
            continue
        rows.append(TicketRow(
            date=date,
            time=parse_time(_row_value(row.select_one(".time"))),
            location=_row_value(row.select_one(".genre")) or None,
            price=row_price(_row_value(row.select_one(".price"))),
            labels=[clean(lab.get_text(" ")) for lab in row.select(".date .label") if clean(lab.get_text(" "))],
        ))
    return rows


# A detail-row label that takes that date out of the programme: a rental
# (TussenTijd at Kikker is "Dans" on the card but "Verhuur" per date), or a
# date that moved / was cancelled.
SKIP_ROW_LABELS = ("verhuur", "verplaatst", "geannuleerd")
# Labels that are not worth showing as annotations.
_QUIET_ROW_LABELS = {"op locatie", *SKIP_ROW_LABELS}


def row_annotations(row: TicketRow | None) -> list[str]:
    return [lab for lab in (row.labels if row else []) if lab.lower() not in _QUIET_ROW_LABELS]


def match_row(rows: list[TicketRow], date: dt.date, time: dt.time | None) -> TicketRow | None:
    """The detail row for one occurrence: same date+time, else same date."""
    exact = [r for r in rows if r.date == date and r.time == time]
    if exact:
        return exact[0]
    same_day = [r for r in rows if r.date == date]
    return same_day[0] if same_day else None


def fetch_all(http: httpx.Client, urls: list[str]) -> dict[str, str]:
    """GET each distinct URL once, ≤ MAX_CONCURRENCY in flight; a URL whose
    fetch fails (non-2xx, network error) is left out of the result — the caller
    then simply has no detail data (price None) for that programme."""
    def get(url: str) -> tuple[str, str | None]:
        try:
            r = http.get(url)
        except httpx.HTTPError:
            return url, None
        return url, r.text if r.status_code == 200 else None

    unique = list(dict.fromkeys(urls))
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        return {u: t for u, t in pool.map(get, unique) if t is not None}
