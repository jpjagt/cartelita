import { describe, it, expect } from "vitest";
import { cellSpan, PRICE_CELLS_DESKTOP, PRICE_CELLS_MOBILE } from "@/lib/price-fit";

describe("cellSpan", () => {
  it("rounds text width (+ paddings) up to whole cells", () => {
    expect(cellSpan(57, 32, { min: 1, max: 9 })).toBe(2); // 64 → 2
    expect(cellSpan(58, 32, { min: 1, max: 9 })).toBe(3); // 65 → 3
  });

  it("clamps to the desktop [3, 5] range", () => {
    expect(cellSpan(20, 32, PRICE_CELLS_DESKTOP)).toBe(3);
    expect(cellSpan(100, 32, PRICE_CELLS_DESKTOP)).toBe(4);
    expect(cellSpan(400, 32, PRICE_CELLS_DESKTOP)).toBe(5);
  });

  it("clamps to the mobile [2, 6] range; empty text takes the minimum", () => {
    expect(cellSpan(0, 24, PRICE_CELLS_MOBILE)).toBe(2);
    expect(cellSpan(85, 24.4, PRICE_CELLS_MOBILE)).toBe(4);
    expect(cellSpan(999, 24, PRICE_CELLS_MOBILE)).toBe(6);
  });

  it("falls back to the minimum before the grid has a cell size", () => {
    expect(cellSpan(100, 0, PRICE_CELLS_DESKTOP)).toBe(3);
  });
});
