import type { NavGeometry, NavPlacement } from "@/lib/types";

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
