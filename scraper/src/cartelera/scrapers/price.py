from __future__ import annotations

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
