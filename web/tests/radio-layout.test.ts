import { describe, it, expect } from "vitest";
import { layoutRadios, radioVars, radioVarsShown } from "@/lib/radio-layout";
import { gridGeometry } from "@/lib/grid-geometry";

describe("layoutRadios", () => {
  it("flows indicator + label + gap left to right", () => {
    expect(layoutRadios([3, 2], { startCol: 5, bandEnd: 45, baseRow: 2, vertical: false })).toEqual([
      { col: 5, span: 3, row: 2 },
      { col: 10, span: 2, row: 2 },
    ]);
  });

  it("wraps an option that would cross the band edge", () => {
    expect(layoutRadios([4, 4, 4], { startCol: 1, bandEnd: 13, baseRow: 2, vertical: false })).toEqual([
      { col: 1, span: 4, row: 2 },
      { col: 7, span: 4, row: 2 },
      { col: 1, span: 4, row: 3 },
    ]);
  });

  it("truncates only a label wider than the whole band", () => {
    expect(layoutRadios([20], { startCol: 1, bandEnd: 9, baseRow: 1, vertical: false })).toEqual([
      { col: 1, span: 7, row: 1 },
    ]);
  });

  it("stacks every other row when vertical", () => {
    expect(layoutRadios([2, 3], { startCol: 1, bandEnd: 40, baseRow: 1, vertical: true })).toEqual([
      { col: 1, span: 2, row: 1 },
      { col: 1, span: 3, row: 3 },
    ]);
  });
});

describe("radioVars", () => {
  it("publishes offsets from the start column, spans and rows", () => {
    // 2.335em at 18px ≈ 42px + 7 → 2 cells of 32px; 3.4em ≈ 61px + 7 → 3.
    const v = radioVars([2.335, 3.4], { baseRow: 2, vertical: false }, gridGeometry(1400, false));
    expect(v).toEqual({
      "--r0c": "0", "--r0s": "2", "--r0r": "2",
      "--r1c": "4", "--r1s": "3", "--r1r": "2",
    });
  });

  it("accounts for a host that starts the group inside the band", () => {
    const g = gridGeometry(390, true); // 16 cells
    const v = radioVars([5, 5], { baseRow: 2, vertical: false, startOffset: 8 }, g);
    // Only 8 cells left: the second option wraps.
    expect(v["--r1r"]).toBe("3");
  });
});

describe("radioVarsShown", () => {
  it("lays out only the shown options, keeping their own indices", () => {
    const g = gridGeometry(1300, false);
    const opts = { baseRow: 4, vertical: false };
    const shown = radioVarsShown([2, 3, 4], [true, false, true], opts, g);
    const all = radioVars([2, 4], opts, g);
    expect(shown["--r0c"]).toBe(all["--r0c"]);
    expect(shown["--r2c"]).toBe(all["--r1c"]);
    expect(shown["--r2r"]).toBe("4");
    expect(shown["--r1c"]).toBeUndefined();
  });
});
