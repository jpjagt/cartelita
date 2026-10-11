import { t } from "@/i18n";
import { gridGeometry, GRID_SCALE, cellTarget } from "@/lib/grid-geometry";
import { cellSpan, PRICE_CELLS_DESKTOP, PRICE_CELLS_MOBILE } from "@/lib/price-fit";
import { renderStepCss, stepTable } from "@/lib/step-table";
import { measureText } from "@/lib/text-metrics";
import type { Locale, PricePageFit } from "@/lib/types";

// BUILD-TIME price column widths (see lib/price-fit.ts for the rule).
//  Desktop: one --price-cells per page, from the widest price; the cell is a
//  fixed 32px there, so it's a single number (Layout.astro sets it on <html>).
//  Narrow: each row spans its own price, and the cell is width / N — so the
//  span can change with the exact width. Rows reference a per-text-width var,
//  --pc: var(--pw<key>), and a per-page step table sets each --pw<key> at
//  every narrow width.

/** The price as an event row shows it (free / sold-out are localized). */
export function displayPrice(price: string | null, locale: Locale): string {
  return price ? (t(locale).prices[price] ?? price) : "";
}

/** Texts of equal advance share one --pw var. */
export function priceKey(text: string): number {
  return Math.round(measureText(text).em * 1000);
}

/** The row's --pc reference, and whether the client must re-measure it (the
    bundled font lacks some of its glyphs). */
export function priceRowVars(text: string): { pc: string; measure: boolean } {
  return { pc: `var(--pw${priceKey(text)})`, measure: !measureText(text).covered };
}

/** Everything a page needs for its price column, given every price text its
    event rows show (all views, filtered rows included — the client fit did
    the same). */
export function pricePageFit(texts: string[]): PricePageFit {
  const ems = new Map<number, number>();
  let widestEm = 0;
  for (const text of new Set(texts)) {
    const m = measureText(text);
    ems.set(priceKey(text), m.em);
    if (m.covered) widestEm = Math.max(widestEm, m.em);
  }
  const widestAll = Math.max(0, ...ems.values());
  const priceCells = cellSpan(widestAll * GRID_SCALE.wide.fontSize, cellTarget(false), PRICE_CELLS_DESKTOP);
  const table = stepTable((width, narrow) => {
    if (!narrow) return {};
    const g = gridGeometry(width, true);
    const out: Record<string, string> = {};
    for (const [key, em] of ems) {
      out[`--pw${key}`] = String(cellSpan(em * g.fontSize, g.cell, PRICE_CELLS_MOBILE));
    }
    return out;
  });
  return { priceCells, coveredEm: widestEm, css: renderStepCss(".gridpaper", table) };
}
