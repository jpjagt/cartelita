import type { RowNumbering } from "@/lib/types";

// The narrow layout's event panel (EventPanel.astro) opens IN the grid flow,
// directly under its event's two rows, so every later row in the day must move
// down by the panel's height. These are the whole-cell row counts behind that.

/** Grid rows one open panel occupies: a 1-cell margin above and below, the
    description (`descRows` lines, omitted when 0) and `actions` one-row
    buttons, with one empty row between consecutive elements. */
export function panelRows(descRows: number, actions: number): number {
  const elements = (descRows > 0 ? 1 : 0) + actions;
  const content = descRows + actions + Math.max(0, elements - 1);
  return 1 + content + 1;
}

/** Number a day's visible rows gap-free: `ev` is the row's index (the CSS
    turns it into grid lines), `po` the extra rows pushed in above it by open
    panels — the sum of `panels` (each row's open-panel height, 0 if closed)
    over the rows before it. The entry after the last row numbers the day's
    trailing spacer. */
export function numberRows(panels: number[], first = 0): RowNumbering[] {
  const out: RowNumbering[] = [];
  let po = 0;
  panels.forEach((rows, i) => {
    out.push({ ev: first + i, po });
    po += rows;
  });
  out.push({ ev: first + panels.length, po });
  return out;
}
