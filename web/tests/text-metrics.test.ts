import { describe, it, expect } from "vitest";
import { measureText } from "@/lib/text-metrics";
import { displayPrice, priceKey, pricePageFit, priceRowVars } from "@/lib/price-css";

describe("measureText", () => {
  it("measures Latin labels in TeX Gyre Heros (Helvetica metrics)", () => {
    // Helvetica advances (units/1000): J 500, a 556, z 500.
    expect(measureText("Jazz").em).toBeCloseTo((500 + 556 + 500 + 500) / 1000, 3);
    expect(measureText("Jazz").covered).toBe(true);
    expect(measureText("").em).toBe(0);
  });

  it("applies kerning, as the browser does", () => {
    const pair = measureText("AV").em;
    expect(pair).toBeLessThan(measureText("A").em + measureText("V").em);
  });

  it("estimates scripts the font lacks and flags them for the client", () => {
    const ru = measureText("Классика");
    expect(ru.covered).toBe(false);
    // Not .notdef boxes (0.28em each): roughly a Latin word of that length.
    expect(ru.em).toBeGreaterThan(8 * 0.4);
    expect(ru.em).toBeLessThan(8 * 0.75);
    const hy = measureText("Ջազ");
    expect(hy.covered).toBe(false);
    expect(hy.em).toBeGreaterThan(measureText("Ջ").em);
  });
});

describe("price fit", () => {
  it("localizes the free / sold-out keys", () => {
    expect(displayPrice("sold-out", "nl")).not.toBe("sold-out");
    expect(displayPrice("12€", "en")).toBe("12€");
    expect(displayPrice(null, "en")).toBe("");
  });

  it("shares one var between prices of equal width (tabular digits)", () => {
    expect(priceKey("12€")).toBe(priceKey("15€"));
    expect(priceRowVars("12€")).toEqual({ pc: `var(--pw${priceKey("12€")})`, measure: false });
    expect(priceRowVars("Бесплатно").measure).toBe(true);
  });

  it("sizes the desktop column from the widest price", () => {
    expect(pricePageFit(["12€", ""]).priceCells).toBe(3);
    // "Uitverkocht" at 18px ≈ 89px + 7 → 4 cells of 32px.
    expect(pricePageFit(["12€", "Uitverkocht"]).priceCells).toBe(4);
    expect(pricePageFit([]).priceCells).toBe(3);
  });

  it("steps each narrow price span with the cell size", () => {
    // Eight digits at 16px: 71.17px + 7 = 78.17px — 4 cells of 24px, but only
    // 3 once the cell reaches 26.06px: N cells over N × 26.06px+, until the
    // next whole cell fits and the cell shrinks back to 24px.
    const text = "00000000";
    const k = priceKey(text);
    const fit = pricePageFit(["12€", text]);
    expect(fit.css).toBe(
      [
        "@media (max-width: 759.98px){",
        `.gridpaper{--pw${priceKey("12€")}:2;--pw${k}:4}`,
        `@container (min-width:208.45px){.gridpaper{--pw${k}:3}}`,
        `@container (min-width:216px){.gridpaper{--pw${k}:4}}`,
        `@container (min-width:234.51px){.gridpaper{--pw${k}:3}}`,
        `@container (min-width:240px){.gridpaper{--pw${k}:4}}`,
        `@container (min-width:260.56px){.gridpaper{--pw${k}:3}}`,
        `@container (min-width:264px){.gridpaper{--pw${k}:4}}`,
        `@container (min-width:286.62px){.gridpaper{--pw${k}:3}}`,
        `@container (min-width:288px){.gridpaper{--pw${k}:4}}`,
        "}",
      ].join("\n"),
    );
  });
});
