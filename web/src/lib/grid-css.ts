import { cssCell, geometryVars, gridGeometry } from "@/lib/grid-geometry";
import { renderStepCss, stepTable } from "@/lib/step-table";

let memo: string | null = null;

/** The .gridpaper geometry step table (inlined in every page's <head> by
    Layout.astro): --cell, --grid-cols, --band-cells, --col-start, the film
    card width/stride and packing flags, per container width. Generated from
    gridGeometry, the same function syncGrid runs — never hand-edited. */
export function gridGeometryCss(): string {
  if (memo) return memo;
  const table = stepTable((width, narrow) => {
    const g = gridGeometry(width, narrow);
    return geometryVars(g, cssCell(g, narrow));
  });
  memo = renderStepCss(".gridpaper", table);
  return memo;
}
