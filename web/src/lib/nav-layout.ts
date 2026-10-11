import type { CssDecls, GridGeometry, LocalePlacement, NavGeometry, NavPlacement } from "@/lib/types";
import { cellSpan, LABEL_CELLS } from "@/lib/price-fit";

// Navbar link packing (Navbar.astro), pure so it can be tested for overlaps.
// Links place onto the one page grid by column line, each spanning the whole
// cells its label needs.

/** Desktop wordmark width in cells (.navbar-wordmark, rows 1–3). */
export const WORDMARK_COLS = 11;
/** Columns kept clear for the locale switcher at the right of row 1. */
const LOCALE_ZONE_MIN = 3;

/** Flow `spans` left to right from `col` on `row`, wrapping DOWN to a new row
    at `end` (exclusive line). A link wider than the whole run is clamped. */
function flowDown(spans: number[], start: number, end: number, row: number): NavPlacement[] {
  let col = start;
  return spans.map((s) => {
    const span = Math.max(1, Math.min(s, end - start));
    if (col + span > end && col > start) {
      row += 1;
      col = start;
    }
    const p = { col, span, row };
    col += span;
    return p;
  });
}

/** Place the genre links.
    Narrow: below the 2-row wordmark from row 3, wrapping down at the band edge.
    Desktop: beside the 3-row wordmark, flowing right on row 3 and wrapping UP
    (3 → 2 → 1) before the locale zone. When that doesn't hold them all (narrow
    desktop band, long labels), they flow below the wordmark from row 4
    instead, wrapping down — never overlapping. */
export function layoutNavLinks(spans: number[], g: NavGeometry): NavPlacement[] {
  if (g.narrow) return flowDown(spans, g.colStart, g.bandEnd, 3);

  const navStart = g.colStart + WORDMARK_COLS;
  const limit = g.bandEnd - Math.max(LOCALE_ZONE_MIN, g.localeCount);
  const beside: NavPlacement[] = [];
  let col = navStart;
  let row = 3;
  for (const span of spans) {
    if (col + span > limit) {
      row -= 1;
      col = navStart;
    }
    if (row < 1 || col + span > limit) {
      return flowDown(spans, g.colStart, g.bandEnd, 4);
    }
    beside.push({ col, span, row });
    col += span;
  }
  return beside;
}

/** Narrow wordmark width in cells (.navbar-wordmark, rows 1–2). */
export const NARROW_WORDMARK_COLS = 9;

/** Place the locale switcher cells.
    Desktop: one cell each, right-aligned on row 1.
    Narrow: packed into the top-right corner beside the 9-col wordmark, flush
    against the band's right edge: right-to-left on row 1, overflow wrapping
    onto row 2 (also right-flush). */
export function layoutLocales(count: number, bandCells: number, narrow: boolean): LocalePlacement[] {
  const out: LocalePlacement[] = [];
  if (!narrow) {
    for (let i = 0; i < count; i++) out.push({ offset: count - i, row: 1 });
    return out;
  }
  const perRow = Math.max(1, bandCells - NARROW_WORDMARK_COLS);
  for (let i = 0; i < count; i++) {
    const row = Math.floor(i / perRow);
    const inRow = i % perRow;
    const rowCount = Math.min(perRow, count - row * perRow);
    // Right-aligned: the row's last cell sits at the band's last column.
    out.push({ offset: rowCount - inRow, row: 1 + row });
  }
  return out;
}

/** The navbar's placement as CSS custom properties on the header, for labels
    `ems` wide (advance at font-size 1px) and a grid of `g`'s geometry. Link i
    reads --n{i}c (columns after --col-start), --n{i}s (span), --n{i}r (row);
    locale i reads --l{i}o (cells before --c-end) and --l{i}r. Shared by the
    build-time step table (Navbar.astro) and the client correction, so both
    produce identical values. */
export function navVars(ems: number[], localeCount: number, g: GridGeometry, narrow: boolean): CssDecls {
  const spans = ems.map((em) => cellSpan(em * g.fontSize, g.cell, LABEL_CELLS));
  const links = layoutNavLinks(spans, { colStart: 1, bandEnd: 1 + g.bandCells, localeCount, narrow });
  const out: CssDecls = {};
  links.forEach((p, i) => {
    out[`--n${i}c`] = String(p.col - 1);
    out[`--n${i}s`] = String(p.span);
    out[`--n${i}r`] = String(p.row);
  });
  layoutLocales(localeCount, g.bandCells, narrow).forEach((p, i) => {
    out[`--l${i}o`] = String(p.offset);
    out[`--l${i}r`] = String(p.row);
  });
  return out;
}
