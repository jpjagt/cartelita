import type { GridGeometry } from "@/lib/types";

// The page grid's geometry, as ONE pure function of the container width and
// the layout mode. It's the single source for both:
//  - the build-time container-query step table (lib/grid-css.ts → Layout.astro),
//    which makes the very first paint correct for the visitor's viewport, and
//  - syncGrid (Layout.astro), the runtime backstop for widths beyond the table
//    and for browsers without container queries.
// Both derive their CSS values from geometryVars below, so they can't disagree.

/** Text size and cell multiplier per layout mode; the target cell is
    round(fontSize × multiplier): 32px desktop, 24px narrow. */
export const GRID_SCALE = {
  wide: { fontSize: 18, multiplier: 1.8 },
  narrow: { fontSize: 16, multiplier: 1.5 },
} as const;

/** Desktop content band width target, in px (snapped to whole cells). */
export const BAND_PX = 1300;
/** Desktop band never narrower than this many cells (when the grid has them). */
export const BAND_MIN_CELLS = 20;
/** Film masonry: a card is at least this many cells wide... */
export const FILM_MIN_CARD = 10;
/** ...with this many cells of gutter between columns. */
export const FILM_GUTTER = 2;

/** Container widths (px) the CSS step table covers, per mode. Outside these,
    syncGrid writes the geometry inline. Narrow only exists below the 760px
    breakpoint; the wide range starts low enough to cover a desktop viewport
    just over 760px minus a classic scrollbar. */
export const GRID_TABLE = {
  narrow: { min: 200, max: 760 },
  wide: { min: 600, max: 4000 },
} as const;

export function cellTarget(narrow: boolean): number {
  const s = narrow ? GRID_SCALE.narrow : GRID_SCALE.wide;
  return Math.round(s.fontSize * s.multiplier);
}

/** Narrow (<760px): no centered band — the content fills the width. Pick the
    whole number of cells that fits at the target, then grow the cell so
    gridCols × cell === width exactly (no sub-cell sliver on the right).
    Desktop: a fixed square cell and a ≈1300px band, centered and snapped to
    whole cells so it always lands on gridlines.
    Film masonry columns are chosen from the band's whole cells: the most
    columns (3, 2) that keep a card ≥ FILM_MIN_CARD cells, else 1. */
export function gridGeometry(width: number, narrow: boolean): GridGeometry {
  const target = cellTarget(narrow);
  const gridCols = Math.max(1, Math.floor(width / target));
  let cell: number, bandCells: number, colStart: number;
  if (narrow) {
    cell = width / gridCols;
    bandCells = gridCols;
    colStart = 1;
  } else {
    cell = target;
    bandCells = Math.min(gridCols, Math.max(BAND_MIN_CELLS, Math.round(BAND_PX / cell)));
    colStart = Math.max(1, Math.round((gridCols - bandCells) / 2) + 1);
  }
  let filmCols = 1;
  let filmWidth = bandCells;
  for (const c of [3, 2]) {
    const w = Math.floor((bandCells - FILM_GUTTER * (c - 1)) / c);
    if (w >= FILM_MIN_CARD) {
      filmCols = c;
      filmWidth = w;
      break;
    }
  }
  return {
    fontSize: narrow ? GRID_SCALE.narrow.fontSize : GRID_SCALE.wide.fontSize,
    cell,
    gridCols,
    bandCells,
    colStart,
    filmCols,
    filmWidth,
  };
}

/** Whether the CSS step table covers this container width in this mode. */
export function inGridTable(width: number, narrow: boolean): boolean {
  const r = narrow ? GRID_TABLE.narrow : GRID_TABLE.wide;
  return width >= r.min && width < r.max;
}

/** The custom properties a .gridpaper carries for geometry `g`. `cell` is the
    CSS value for --cell: the step table passes `calc(100cqw / N)` in narrow
    mode (exact fill of the container, whatever its fractional width); the JS
    backstop passes the px value it computed from the same width.
    --fc3/--fc2/--fc1 are 0/1 flags selecting the film masonry packing (CSS
    can't branch on a number, but it can multiply by one). */
export function geometryVars(g: GridGeometry, cell: string = `${g.cell}px`): Record<string, string> {
  return {
    "--font-size": `${g.fontSize}px`,
    "--cell": cell,
    "--grid-cols": String(g.gridCols),
    "--band-cells": String(g.bandCells),
    "--col-start": String(g.colStart),
    "--film-width": String(g.filmWidth),
    "--fc3": String(+(g.filmCols === 3)),
    "--fc2": String(+(g.filmCols === 2)),
    "--fc1": String(+(g.filmCols === 1)),
  };
}

/** --cell as the step table writes it: exact-fill in narrow mode. */
export function cssCell(g: GridGeometry, narrow: boolean): string {
  return narrow ? `calc(100cqw / ${g.gridCols})` : `${g.cell}px`;
}
