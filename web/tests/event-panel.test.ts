import { describe, it, expect } from "vitest";
import { panelRows, numberRows } from "@/lib/event-panel";

describe("panelRows", () => {
  it("adds 1-cell margins and 1-cell gaps between elements", () => {
    // margin + 3 actions + 2 gaps + margin
    expect(panelRows(0, 3)).toBe(7);
    // margin + 3 desc lines + gap + 3 actions + 2 gaps + margin
    expect(panelRows(3, 3)).toBe(11);
    expect(panelRows(1, 3)).toBe(9);
  });
});

describe("numberRows", () => {
  it("numbers rows gap-free with no panels open", () => {
    expect(numberRows([0, 0, 0])).toEqual([
      { ev: 0, po: 0 },
      { ev: 1, po: 0 },
      { ev: 2, po: 0 },
      { ev: 3, po: 0 }, // spacer
    ]);
  });

  it("pushes rows after an open panel down by its height", () => {
    expect(numberRows([0, 9, 0])).toEqual([
      { ev: 0, po: 0 },
      { ev: 1, po: 0 },
      { ev: 2, po: 9 },
      { ev: 3, po: 9 },
    ]);
  });

  it("accumulates several panels and honours a start index", () => {
    expect(numberRows([7, 0, 9], 1)).toEqual([
      { ev: 1, po: 0 },
      { ev: 2, po: 7 },
      { ev: 3, po: 7 },
      { ev: 4, po: 16 },
    ]);
  });
});
