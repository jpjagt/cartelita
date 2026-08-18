from __future__ import annotations
import re

# Shared price-display helpers for scrapers.
#
# Price convention (see the writing-a-scraper skill): only show a "lo–hi€" range
# when the tiers differ meaningfully for the user. Rule of thumb: if the high price
# point is < 2× the low, the spread is minor — don't emit a range, just show the
# highest price. A range is reserved for genuinely large spreads (high >= 2× low),
# which for our concert halls means real seating-tier differences worth surfacing.

# A high price that is 2x or more the low is a "meaningful" spread worth a range.
_RANGE_FACTOR = 2


def format_eur_range(lo: int, hi: int) -> str:
    """Render a euro price from its low/high integer-euro bounds.

    `"{hi}€"` when the spread is minor (a single price, or high < 2× low); a
    `"{lo}–{hi}€"` range only when high >= 2× low. Assumes 0 <= lo <= hi."""
    if hi <= 0:
        return f"{hi}€"
    if lo == hi or hi < _RANGE_FACTOR * lo:
        return f"{hi}€"
    return f"{lo}–{hi}€"


def format_amd_range(lo: int, hi: int) -> str:
    """Render an Armenian-dram price from its low/high integer bounds.

    Same 2x-spread rule as format_eur_range, with the dram symbol appended in
    the €-style ("5000֏", range "2500–5000֏")."""
    if hi <= 0:
        return f"{hi}֏"
    if lo == hi or hi < _RANGE_FACTOR * lo:
        return f"{hi}֏"
    return f"{lo}–{hi}֏"


# A trailing dram unit in source free text: " AMD" (any case, word-bounded) or
# a spaced "֏" — both normalize to the bare symbol glued to the number.
_AMD_UNIT_RE = re.compile(r"\s*(?:\bAMD\b|֏)", re.IGNORECASE)


def normalize_amd(text: str) -> str:
    """Rewrite free-text dram prices to the symbol convention: "5000 AMD" and
    "5000 ֏" both become "5000֏". Text without a dram unit passes through
    untouched (e.g. "Tickets at the bar")."""
    return _AMD_UNIT_RE.sub("֏", text)
