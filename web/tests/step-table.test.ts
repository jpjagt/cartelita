import { describe, it, expect } from "vitest";
import { renderStepCss, stepTable } from "@/lib/step-table";
import { gridGeometryCss } from "@/lib/grid-css";
import { cssCell, geometryVars, gridGeometry, GRID_TABLE } from "@/lib/grid-geometry";
import type { CssDecls, StepFn, StepTable } from "@/lib/types";

// What the CSS cascade resolves at container width `w`: the base, then every
// @container rule whose min-width ≤ w, in source (ascending) order.
function resolve(t: StepTable, w: number, narrow: boolean): CssDecls {
  const sweep = narrow ? t.narrow : t.wide;
  const out = { ...sweep.base };
  for (const s of sweep.steps) if (s.minWidth <= w) Object.assign(out, s.decls);
  return out;
}

const geometryFn: StepFn = (w, narrow) => {
  const g = gridGeometry(w, narrow);
  return geometryVars(g, cssCell(g, narrow));
};

describe("stepTable", () => {
  it("reproduces the grid geometry at every covered width", () => {
    const t = stepTable(geometryFn);
    for (const narrow of [true, false]) {
      const r = narrow ? GRID_TABLE.narrow : GRID_TABLE.wide;
      for (let w = r.min; w < r.max; w += 0.5) {
        expect(resolve(t, w, narrow)).toEqual(geometryFn(w, narrow));
      }
    }
  });

  it("emits only the declarations that change, at ascending widths", () => {
    const t = stepTable(geometryFn);
    const widths = t.wide.steps.map((s) => s.minWidth);
    expect(widths).toEqual([...widths].sort((a, b) => a - b));
    // Desktop steps every 32px; the band saturates at 41 cells, after which
    // only the start column (and grid width) move.
    const late = t.wide.steps.find((s) => s.minWidth === 1600)!;
    expect(late.decls).toEqual({ "--grid-cols": "50", "--col-start": "6" });
  });

  it("locates fractional thresholds to within 0.01px", () => {
    // A value that flips at a non-integer width.
    const fn: StepFn = (w) => ({ "--x": w >= 300.3712 ? "b" : "a" });
    const t = stepTable(fn, { narrow: { min: 200, max: 400 }, wide: { min: 200, max: 400 } });
    expect(t.narrow.steps).toEqual([{ minWidth: 300.38, decls: { "--x": "b" } }]);
  });

  it("walks several changes inside one pixel", () => {
    const fn: StepFn = (w) => ({ "--a": w >= 300.2 ? "1" : "0", "--b": w >= 300.7 ? "1" : "0" });
    const t = stepTable(fn, { narrow: { min: 290, max: 310 }, wide: { min: 290, max: 310 } });
    expect(t.wide.steps.map((s) => s.minWidth)).toEqual([300.2, 300.7]);
    for (const w of [299, 300.25, 300.5, 300.75, 305]) expect(resolve(t, w, false)).toEqual(fn(w, false));
  });
});

describe("renderStepCss", () => {
  it("wraps each mode in the breakpoint and each step in a container query", () => {
    const fn: StepFn = (w, narrow) => (narrow ? { "--n": w >= 300 ? "2" : "1" } : { "--w": w >= 1000 ? "2" : "1" });
    const css = renderStepCss(".x", stepTable(fn));
    expect(css).toBe(
      [
        "@media not all and (max-width: 759.98px){",
        ".x{--w:1}",
        "@container (min-width:1000px){.x{--w:2}}",
        "}",
        "@media (max-width: 759.98px){",
        ".x{--n:1}",
        "@container (min-width:300px){.x{--n:2}}",
        "}",
      ].join("\n"),
    );
  });

  it("skips a mode with nothing to say", () => {
    const css = renderStepCss(".x", stepTable((_, narrow) => (narrow ? { "--n": "1" } : {})));
    expect(css).toBe("@media (max-width: 759.98px){\n.x{--n:1}\n}");
  });
});

describe("gridGeometryCss", () => {
  const css = gridGeometryCss();
  it("sets exact-fill narrow cells and fixed desktop cells", () => {
    expect(css).toContain("@container (min-width:384px){.gridpaper{--cell:calc(100cqw / 16);--grid-cols:16;--band-cells:16");
    expect(css).toContain(".gridpaper{--font-size:18px;--cell:32px;");
    expect(css).not.toContain("32.4");
  });
  it("stays small enough to inline", () => {
    expect(css.length).toBeLessThan(12_000);
  });
});
