"""Small helpers shared by the Rotterdam venue scrapers (BIRD, Rotown, Baroeg,
WORM, Annabel, Toffler, Maassilo, Roodkapje): a polite GET, month names,
year inference and time extraction. Euro price helpers live in `price.py`,
the Cartelita User-Agent in `http.py`.

The leading underscore keeps `load_all()` from importing this as a scraper.
"""

from __future__ import annotations

import datetime as dt
import re

from cartelera.scrapers.http import CARTELITA_COMPAT_UA, fetch

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
    return fetch(url, headers={"User-Agent": CARTELITA_COMPAT_UA})


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


_TIME = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")


def first_time(text: str | None) -> dt.time | None:
    """The first HH:MM / HH.MM in `text`."""
    if not text:
        return None
    m = _TIME.search(text)
    return dt.time(int(m.group(1)), int(m.group(2))) if m else None
