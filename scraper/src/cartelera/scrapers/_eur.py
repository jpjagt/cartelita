"""Euro-amount helpers shared by the Utrecht scrapers (batch 6).

Dutch venues state prices as `€ 15.5`, `€15,50`, `19.50` (JSON-LD) — this
normalizes them to the house convention: `"15,50€"`, whole euros without
cents (`"9€"`). Private module (leading underscore): skipped by `load_all()`.
"""

from __future__ import annotations

import re

# "€ 15.5", "€15,50", "15,50 €", "€ 0.00" — the euro sign on either side. The
# trailing-sign form must not start mid-number or mid-time ("23:30 €15" is 15,
# not 30).
_EUR_AMOUNT = re.compile(
    r"€\s*(\d{1,4}(?:[.,]\d{1,2})?)|(?<![\d:.,])(\d{1,4}(?:[.,]\d{1,2})?)\s*€"
)

# Polite, honest identification (docs/nl-cities-plan.md): a browser token for
# sites that gate on it, plus the Cartelita marker and URL.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 "
    "Cartelita (+https://cartelita.july.dev)"
)
HEADERS = {"User-Agent": USER_AGENT}


def to_float(raw: str) -> float:
    return float(raw.replace(",", "."))


def format_eur(value: float) -> str:
    """15.5 → "15,50€", 9.0 → "9€", 0 → "free"."""
    if value <= 0:
        return "free"
    cents = round(value * 100)
    if cents % 100 == 0:
        return f"{cents // 100}€"
    return f"{cents // 100},{cents % 100:02d}€"


def eur_amounts(text: str) -> list[float]:
    """Every €-marked amount in `text`, in order."""
    return [to_float(a or b) for a, b in _EUR_AMOUNT.findall(text)]
