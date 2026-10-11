import { describe, it, expect } from "vitest";
import {
  cellTarget,
  cssCell,
  geometryVars,
  gridGeometry,
  inGridTable,
  GRID_TABLE,
} from "@/lib/grid-geometry";

// Verbatim port of the syncGrid geometry this replaced (Layout.astro before the
// CSS step table), kept independent of the implementation under test.
function legacy(width: number, narrow: boolean) {
  const target = Math.round(narrow ? 16 * 1.5 : 18 * 1.8);
  let cell, gridCols, bandCells, colStart;
  if (narrow) {
    gridCols = Math.max(1, Math.floor(width / target));
    cell = width / gridCols;
    bandCells = gridCols;
    colStart = 1;
  } else {
    cell = target;
    gridCols = Math.max(1, Math.floor(width / cell));
    bandCells = Math.min(gridCols, Math.max(20, Math.round(1300 / cell)));
    colStart = Math.max(1, Math.round((gridCols - bandCells) / 2) + 1);
  }
  let filmCols = 1;
  let cardW = bandCells;
  for (const c of [3, 2]) {
    const w = Math.floor((bandCells - 2 * (c - 1)) / c);
    if (w >= 10) {
      filmCols = c;
      cardW = w;
      break;
    }
  }
  return { cell, gridCols, bandCells, colStart, filmCols, filmWidth: cardW };
}

describe("gridGeometry", () => {
  it("targets 32px desktop and 24px narrow cells (no 32.4px fallback)", () => {
    expect(cellTarget(false)).toBe(32);
    expect(cellTarget(true)).toBe(24);
  });

  it("matches the legacy syncGrid at every width, incl. fractional ones", () => {
    for (let w = 100; w <= 4200; w += 0.25) {
      for (const narrow of [true, false]) {
        const { fontSize, ...g } = gridGeometry(w, narrow);
        expect(g).toEqual(legacy(w, narrow));
        expect(fontSize).toBe(narrow ? 16 : 18);
      }
    }
  });

  it("fills a phone exactly with whole cells", () => {
    const g = gridGeometry(390, true);
    expect(g).toMatchObject({ gridCols: 16, bandCells: 16, colStart: 1, filmCols: 1 });
    expect(g.cell * g.gridCols).toBeCloseTo(390, 10);
  });

  it("centers a ≈1300px band on desktop", () => {
    expect(gridGeometry(1400, false)).toMatchObject({ cell: 32, gridCols: 43, bandCells: 41, colStart: 2, filmCols: 3, filmWidth: 12 });
    expect(gridGeometry(1000, false)).toMatchObject({ gridCols: 31, bandCells: 31, colStart: 1, filmCols: 2, filmWidth: 14 });
  });

  it("drops film columns as the band narrows", () => {
    expect(gridGeometry(34 * 32, false).filmCols).toBe(3);
    expect(gridGeometry(34 * 32 - 1, false).filmCols).toBe(2);
    expect(gridGeometry(22 * 32, false).filmCols).toBe(2);
    expect(gridGeometry(22 * 32 - 1, false).filmCols).toBe(1);
  });
});

describe("geometryVars", () => {
  it("publishes integers and exactly one film packing flag", () => {
    const v = geometryVars(gridGeometry(1000, false));
    expect(v).toMatchObject({
      "--font-size": "18px",
      "--cell": "32px",
      "--grid-cols": "31",
      "--band-cells": "31",
      "--col-start": "1",
      "--film-width": "14",
      "--fc3": "0",
      "--fc2": "1",
      "--fc1": "0",
    });
  });

  it("writes the narrow cell as an exact fill of the container in CSS", () => {
    const g = gridGeometry(390, true);
    expect(cssCell(g, true)).toBe("calc(100cqw / 16)");
    expect(cssCell(gridGeometry(1400, false), false)).toBe("32px");
    expect(geometryVars(g)["--cell"]).toBe("24.375px"); // the JS backstop's value
  });
});

describe("inGridTable", () => {
  it("covers phones and desktops, not the extremes", () => {
    expect(inGridTable(390, true)).toBe(true);
    expect(inGridTable(GRID_TABLE.narrow.min - 1, true)).toBe(false);
    expect(inGridTable(1400, false)).toBe(true);
    expect(inGridTable(GRID_TABLE.wide.max, false)).toBe(false);
  });
});
