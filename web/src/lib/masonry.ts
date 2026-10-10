import type { MasonryLayout } from "@/lib/types";

/** Shortest-column masonry packing over `cols` columns, in the given card
    order. Returns, per card, the chosen column and its starting row offset,
    plus the total rows consumed (the tallest column). Ties pick the leftmost
    column to preserve left-to-right reading order. */
function pack(
  heights: number[],
  cols: number,
): { placed: { col: number; row: number }[]; rows: number } {
  const colHeights = new Array(cols).fill(0);
  const placed = heights.map((height) => {
    let col = 0;
    for (let c = 1; c < cols; c++) {
      if (colHeights[c] < colHeights[col]) col = c;
    }
    const row = colHeights[col];
    colHeights[col] += height + 1; // + 1-cell gutter between cards
    return { col, row };
  });
  // Each column ends with a trailing gutter; the consumed rows is the tallest
  // column minus that final gutter (0 when there are no cards).
  const rows = Math.max(0, ...colHeights.map((h) => Math.max(0, h - 1)));
  return { placed, rows };
}

/** Single-column (mobile) stack: cards in order, one gutter row between them.
    Returns the row offset per card and total rows. */
function stackSingle(heights: number[]): { rows1: number[]; total: number } {
  let acc = 0;
  const rows1 = heights.map((height) => {
    const at = acc;
    acc += height + 1;
    return at;
  });
  return { rows1, total: Math.max(0, acc - 1) };
}

/** Pack cards of the given heights (in cells) into the 3-column, 2-column and
    single-column layouts the card CSS (.gc-film-card) selects between. Used by
    the film "by film" view and the My list venue directory. */
export function packCards(heights: number[]): MasonryLayout {
  const p3 = pack(heights, 3);
  const p2 = pack(heights, 2);
  const single = stackSingle(heights);
  return {
    placements: heights.map((_, i) => ({
      col3: p3.placed[i].col,
      row3: p3.placed[i].row,
      col2: p2.placed[i].col,
      row2: p2.placed[i].row,
      row1: single.rows1[i],
    })),
    rows3: p3.rows,
    rows2: p2.rows,
    rows1: single.total,
  };
}
