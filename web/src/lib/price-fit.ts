// Whole-cell text spans. The price column fits its text in whole cells (e.g.
// NL "Uitverkocht" needs more than the 3-cell default). Desktop picks one width per page so the
// columns stay aligned; mobile sizes each row on its own (EventRow.astro).
// Navbar links and radio labels use the same rule (LABEL_CELLS).

/** Desktop price column bounds, in cells. */
export const PRICE_CELLS_DESKTOP = { min: 3, max: 5 } as const;
/** Mobile (per-row) price span bounds, in cells. */
export const PRICE_CELLS_MOBILE = { min: 2, max: 6 } as const;
/** Text labels (navbar links, radio labels): at least one cell, no cap. */
export const LABEL_CELLS = { min: 1, max: Infinity } as const;

/** Whole cells a text run of `textPx` needs: the cell's 3px side paddings plus
    1px of sub-pixel slack (measured widths are fractional), clamped. */
export function cellSpan(
  textPx: number,
  cellPx: number,
  { min, max }: { min: number; max: number },
): number {
  if (!(cellPx > 0)) return min;
  const span = textPx > 0 ? Math.ceil((textPx + 7) / cellPx) : 0;
  return Math.min(max, Math.max(min, span));
}
