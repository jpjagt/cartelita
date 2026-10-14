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

/** A collapsed day (its header toggled shut): every row hidden, one note row
    ("Events hidden — click to show") in their place, then the spacer. The
    note takes row index 0 like the first event would; the spacer the next.
    Narrow, an event spans two grid rows but the note only one, so the
    spacer's `po` pulls it back up a row there (desktop row formulas ignore
    `po`) — header, note, one blank row, in both layouts. */
export function numberCollapsed(): { note: RowNumbering; spacer: RowNumbering } {
  return { note: { ev: 0, po: 0 }, spacer: { ev: 1, po: -1 } };
}

/** Window event announcing a day was just collapsed (detail: its section), so
    an open event panel or share menu in it closes (EventPanel, ShareMenu). */
export const DAY_COLLAPSE_EVENT = "daycollapse";
