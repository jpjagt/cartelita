"""Small helpers shared by the Rotterdam venue scrapers (BIRD, Rotown, Baroeg,
WORM, Annabel, Toffler, Maassilo, Roodkapje).

The leading underscore keeps `load_all()` from importing this as a scraper.
"""

from __future__ import annotations

import datetime as dt
import re

from cartelera.scrapers.http import fetch

# Honest, stable identification (see docs/nl-cities-plan.md). The leading
# "Mozilla/5.0 (compatible; ...)" keeps naive UA filters happy without
# pretending to be a browser.
USER_AGENT = "Mozilla/5.0 (compatible; Cartelita (+https://cartelita.july.dev))"

DUTCH_MONTHS = {
    "januari": 1, "jan": 1, "februari": 2, "feb": 2, "maart": 3, "mrt": 3,
    "april": 4, "apr": 4, "mei": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7,
    "augustus": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
ENGLISH_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def get(url: str, *, impersonate: bool = False) -> str:
    """GET `url` with the Cartelita User-Agent; raise on a non-2xx status."""
    if impersonate:
        return fetch(url, impersonate=True)
    return fetch(url, headers={"User-Agent": USER_AGENT})


def infer_year(month: int, day: int, today: dt.date) -> dt.date | None:
    """A year-less programme date ("vrijdag 16 oktober") → the next occurrence
    on or after ~2 months before `today` (agenda pages list upcoming events;
    the slack keeps a just-past event in the current year)."""
    for year in (today.year, today.year + 1):
        try:
            d = dt.date(year, month, day)
        except ValueError:
            continue
        if d >= today - dt.timedelta(days=60):
            return d
    return None


# An amount in euro free text: "€25,-", "€ 26,50", "33,75", "14.95", "20".
_AMOUNT = re.compile(r"(\d{1,4})(?:[.,](\d{2}|-))?(?!\d)")


_EURO_AMOUNT = re.compile(r"€\s*" + _AMOUNT.pattern)


def _amounts(text: str, require_symbol: bool = False) -> list[float]:
    out: list[float] = []
    pattern = _EURO_AMOUNT if require_symbol else _AMOUNT
    for whole, frac in pattern.findall(text):
        cents = 0 if frac in ("", "-") else int(frac)
        out.append(int(whole) + cents / 100)
    return out


def format_eur(amount: float) -> str:
    """12.5 → "12,50€", 25.0 → "25€" (Dutch decimal comma)."""
    if amount == int(amount):
        return f"{int(amount)}€"
    return f"{amount:.2f}".replace(".", ",") + "€"


def eur_price(text: str | None, *, require_symbol: bool = False) -> str | None:
    """Normalize a euro price statement to the price convention.

    One amount → that amount; several (presale/door, early bird/regular, a
    "€28 - €45" spread) → the highest, or a "lo–hi€" range only when the high
    is at least twice the low. Zero → "free". No amount → None (callers
    handle "gratis"/"uitverkocht" wording themselves). `require_symbol` only
    counts amounts written after a "€" (for prose with other numbers in it)."""
    if not text:
        return None
    amounts = [a for a in _amounts(text, require_symbol) if a < 1000]
    if not amounts:
        return None
    lo, hi = min(amounts), max(amounts)
    if hi == 0:
        return "free"
    if lo > 0 and hi >= 2 * lo:
        return f"{format_eur(lo)[:-1]}–{format_eur(hi)}"
    return format_eur(hi)


_TIME = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")


def first_time(text: str | None) -> dt.time | None:
    """The first HH:MM / HH.MM in `text`."""
    if not text:
        return None
    m = _TIME.search(text)
    return dt.time(int(m.group(1)), int(m.group(2))) if m else None
