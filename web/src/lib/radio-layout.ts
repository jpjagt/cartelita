import { cellSpan, LABEL_CELLS } from "@/lib/price-fit";
import type { CssDecls, GridGeometry, RadioGeometry, RadioPlacement } from "@/lib/types";

// GridRadioButtons packing, pure: each option is one indicator cell + a label
// spanning the whole cells its text needs, laid out onto the parent grid by
// column line. Shared by the build-time step table (GridRadioButtons.astro)
// and the client correction, so both produce identical placements.

/** Horizontal: options flow left to right with a one-cell gap, wrapping to
    the next row when one would cross the band's right edge (only a label
    wider than the whole band truncates). Vertical: one option every other row. */
export function layoutRadios(spans: number[], g: RadioGeometry): RadioPlacement[] {
  let col = g.startCol;
  let row = g.baseRow;
  return spans.map((s) => {
    if (!g.vertical && col > g.startCol && col + 1 + s > g.bandEnd) {
      row += 1;
      col = g.startCol;
    }
    const span = Math.max(1, Math.min(s, g.bandEnd - col - 1));
    const p = { col, span, row };
    if (g.vertical) row += 2;
    else col += 1 + span + 1; // indicator + label + one-cell gap
    return p;
  });
}

/** The group's placement as CSS custom properties: option i's indicator sits
    --r{i}c columns after the start column, its label spans --r{i}s, both on
    row --r{i}r. `ems` are the labels' advances at font-size 1px; the group
    starts `startOffset` columns after the band's start (--col-start). */
export function radioVars(
  ems: number[],
  opts: { baseRow: number; vertical: boolean; startOffset?: number },
  g: GridGeometry,
): CssDecls {
  const spans = ems.map((em) => cellSpan(em * g.fontSize, g.cell, LABEL_CELLS));
  const placed = layoutRadios(spans, {
    startCol: 1,
    bandEnd: 1 + g.bandCells - (opts.startOffset ?? 0),
    baseRow: opts.baseRow,
    vertical: opts.vertical,
  });
  const out: CssDecls = {};
  placed.forEach((p, i) => {
    out[`--r${i}c`] = String(p.col - 1);
    out[`--r${i}s`] = String(p.span);
    out[`--r${i}r`] = String(p.row);
  });
  return out;
}
