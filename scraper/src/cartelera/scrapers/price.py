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


# --- Euro amounts in free text (Dutch venues) --------------------------------
#
# Dutch sites state prices as "€ 15.5", "€15,50", "€25,-", "19.50" (JSON-LD).
# These normalize them to the house convention: "15,50€" (decimal comma), whole
# euros without cents ("9€"), zero → "free".

# A €-marked amount, the euro sign on either side: "€ 15.5", "€15,50",
# "15,50 €". The trailing-sign form must not start mid-number or mid-time
# ("23:30 €15" is 15, not 30).
_EUR_MARKED = re.compile(
    r"€\s*(\d{1,4}(?:[.,]\d{1,2})?)|(?<![\d:.,])(\d{1,4}(?:[.,]\d{1,2})?)\s*€"
)

# Any amount in euro free text, sign optional: "€25,-", "€ 26,50", "33,75",
# "14.95", "20".
_AMOUNT = re.compile(r"(\d{1,4})(?:[.,](\d{2}|-))?(?!\d)")
_AMOUNT_AFTER_EUR = re.compile(r"€\s*" + _AMOUNT.pattern)


def eur_to_float(raw: str) -> float:
    """"15,50" / "15.5" → 15.5."""
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
    return [eur_to_float(a or b) for a, b in _EUR_MARKED.findall(text)]


def _loose_amounts(text: str, require_symbol: bool) -> list[float]:
    out: list[float] = []
    pattern = _AMOUNT_AFTER_EUR if require_symbol else _AMOUNT
    for whole, frac in pattern.findall(text):
        cents = 0 if frac in ("", "-") else int(frac)
        out.append(int(whole) + cents / 100)
    return out


def eur_price(text: str | None, *, require_symbol: bool = False) -> str | None:
    """Normalize a euro price statement to the price convention.

    One amount → that amount; several (presale/door, early bird/regular, a
    "€28 - €45" spread) → the highest, or a "lo–hi€" range only when the high
    is at least twice the low. Zero → "free". No amount → None (callers
    handle "gratis"/"uitverkocht" wording themselves). Amounts need no "€"
    unless `require_symbol` (for prose with other numbers in it)."""
    if not text:
        return None
    amounts = [a for a in _loose_amounts(text, require_symbol) if a < 1000]
    if not amounts:
        return None
    lo, hi = min(amounts), max(amounts)
    if hi == 0:
        return "free"
    if lo > 0 and hi >= _RANGE_FACTOR * lo:
        return f"{format_eur(lo)[:-1]}–{format_eur(hi)}"
    return format_eur(hi)
