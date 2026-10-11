import { describe, it, expect } from "vitest";
import { layoutLocales, layoutNavLinks, navVars, WORDMARK_COLS } from "@/lib/nav-layout";
import { gridGeometry } from "@/lib/grid-geometry";
import type { NavPlacement } from "@/lib/types";

// Two placements overlap when they share a row and their column ranges meet.
function overlaps(ps: NavPlacement[]): boolean {
  return ps.some((a, i) =>
    ps.slice(i + 1).some(
      (b) => a.row === b.row && a.col < b.col + b.span && b.col < a.col + a.span,
    ),
  );
}

// Amsterdam EN: 7 categories + My list.
const AMS = [3, 4, 4, 3, 3, 2, 5, 3];

describe("layoutNavLinks", () => {
  it("flows beside the wordmark on row 3 when there's room", () => {
    const ps = layoutNavLinks([3, 4], { colStart: 5, bandEnd: 45, localeCount: 2, narrow: false });
    expect(ps).toEqual([
      { col: 5 + WORDMARK_COLS, span: 3, row: 3 },
      { col: 5 + WORDMARK_COLS + 3, span: 4, row: 3 },
    ]);
  });

  it("wraps up a row before the locale zone", () => {
    const ps = layoutNavLinks(AMS, { colStart: 1, bandEnd: 33, localeCount: 2, narrow: false });
    expect(Math.min(...ps.map((p) => p.row))).toBeGreaterThanOrEqual(1);
    expect(ps.every((p) => p.row <= 3)).toBe(true);
    expect(ps.every((p) => p.col + p.span <= 33 - 3)).toBe(true);
    expect(overlaps(ps)).toBe(false);
  });

  it("falls back below the wordmark when three rows don't hold the links", () => {
    // 23 columns: 9 beside the wordmark minus the locale zone — too few.
    const ps = layoutNavLinks(AMS, { colStart: 1, bandEnd: 24, localeCount: 2, narrow: false });
    expect(ps[0]).toEqual({ col: 1, span: 3, row: 4 });
    expect(ps.every((p) => p.row >= 4 && p.col + p.span <= 24)).toBe(true);
    expect(overlaps(ps)).toBe(false);
  });

  it("never overlaps at any desktop band width", () => {
    for (let cols = 20; cols <= 60; cols++) {
      const ps = layoutNavLinks(AMS, { colStart: 1, bandEnd: 1 + cols, localeCount: 3, narrow: false });
      expect(overlaps(ps), `cols=${cols}`).toBe(false);
      // Beside the wordmark (rows 1–3) a link must stay right of it.
      for (const p of ps) {
        if (p.row <= 3) expect(p.col).toBeGreaterThanOrEqual(1 + WORDMARK_COLS);
      }
    }
  });

  it("narrow: flows from the band start on row 3, wrapping down", () => {
    const ps = layoutNavLinks(AMS, { colStart: 1, bandEnd: 17, localeCount: 2, narrow: true });
    expect(ps[0]).toEqual({ col: 1, span: 3, row: 3 });
    expect(ps.every((p) => p.col + p.span <= 17)).toBe(true);
    expect(overlaps(ps)).toBe(false);
  });
});

describe("layoutLocales", () => {
  it("desktop: one cell each, right-aligned on row 1", () => {
    expect(layoutLocales(3, 41, false)).toEqual([
      { offset: 3, row: 1 },
      { offset: 2, row: 1 },
      { offset: 1, row: 1 },
    ]);
  });

  it("narrow: right-flush beside the wordmark, overflow onto row 2", () => {
    // 16 cells: 7 beside the 9-col wordmark — all three on row 1.
    expect(layoutLocales(3, 16, true)).toEqual([
      { offset: 3, row: 1 },
      { offset: 2, row: 1 },
      { offset: 1, row: 1 },
    ]);
    // 11 cells: 2 per row.
    expect(layoutLocales(3, 11, true)).toEqual([
      { offset: 2, row: 1 },
      { offset: 1, row: 1 },
      { offset: 1, row: 2 },
    ]);
  });
});

describe("navVars", () => {
  // "Jazz" 2.056em, "My list" ≈ 2.828em.
  const ems = [2.056, 2.828];

  it("places links relative to --col-start, never on absolute lines", () => {
    const wide = navVars(ems, 3, gridGeometry(1400, false), false);
    // 1400px: --col-start 2, but offsets are band-relative.
    expect(wide).toMatchObject({ "--n0c": String(WORDMARK_COLS), "--n0s": "2", "--n0r": "3" });
    expect(wide["--n1c"]).toBe(String(WORDMARK_COLS + 2));
    expect(navVars(ems, 3, gridGeometry(2000, false), false)).toEqual(wide);
  });

  it("spans whole cells of the narrow cell at the exact width", () => {
    // 16px "My list" ≈ 45.2px + 7 → 3 cells of 24px …
    expect(navVars(ems, 2, gridGeometry(384, true), true)["--n1s"]).toBe("3");
    // … but 2 cells once the cell grows past 26.1px (e.g. 8 cells over 210px).
    expect(navVars(ems, 2, gridGeometry(215, true), true)["--n1s"]).toBe("2");
  });

  it("publishes the locale cells", () => {
    const v = navVars(ems, 2, gridGeometry(1000, false), false);
    expect(v).toMatchObject({ "--l0o": "2", "--l0r": "1", "--l1o": "1", "--l1r": "1" });
  });
});
