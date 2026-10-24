"""Dates written without a year ("Wednesday 25 November", "Mon 26th
October") — shared by the London venues whose pages leave the year out.

The weekday pins the year: within a few years after an anchor date (today,
or the day the event was announced), a given day-month falls on a given
weekday in only one year. Without a weekday, the first occurrence on or
after the anchor is taken.

Private module (leading underscore): skipped by `load_all()`.
"""

from __future__ import annotations

import datetime as dt
import re

MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"), start=1)}
WEEKDAYS = {d: i for i, d in enumerate(
    ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"))}
# How far after the anchor a yearless date may lie.
HORIZON_YEARS = 3

# "Wednesday 25 November", "Mon 26th October", "Sat 7th Nov"
_DAY_MONTH = re.compile(
    r"(?i)\b(?:(mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\b"
)


def resolve(day: int, month: int, anchor: dt.date, weekday: int | None = None) -> dt.date | None:
    """The date `day`/`month` on or after `anchor` (within HORIZON_YEARS)
    whose weekday is `weekday` (0 = Monday) — or the first one at all when
    no weekday is given. None when no year fits."""
    for year in range(anchor.year, anchor.year + HORIZON_YEARS + 1):
        try:
            date = dt.date(year, month, day)
        except ValueError:  # 29 February
            continue
        if date < anchor:
            continue
        if weekday is None or date.weekday() == weekday:
            return date
    return None


def parse(text: str, anchor: dt.date) -> dt.date | None:
    """The first "[weekday] day month" in `text`, its year resolved against
    `anchor` (see resolve). None when there is none or no year fits."""
    for m in _DAY_MONTH.finditer(text):
        month = next((n for name, n in MONTHS.items() if name.startswith(m.group(3).lower())
                      and len(m.group(3)) >= 3), None)
        if month is None:
            continue
        weekday = None
        if m.group(1):
            weekday = next(n for name, n in WEEKDAYS.items() if name.startswith(m.group(1).lower()))
        return resolve(int(m.group(2)), month, anchor, weekday)
    return None


def parse_time(text: str) -> dt.time | None:
    """The first clock time in `text`: "1.10pm", "7:00pm", "7pm", "10am",
    "19:30"."""
    m = re.search(r"(?i)\b(\d{1,2})(?:[.:](\d{2}))?\s*(am|pm)\b", text)
    if m:
        hour, minute = int(m.group(1)) % 12, int(m.group(2) or 0)
        if m.group(3).lower() == "pm":
            hour += 12
        return dt.time(hour, minute) if hour < 24 and minute < 60 else None
    m = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    return dt.time(int(m.group(1)), int(m.group(2))) if m else None
