import { describe, it, expect } from "vitest";
import {
  fitTabs,
  flowLines,
  layoutNav,
  MIN_BESIDE_TABS,
  NARROW_WORDMARK_COLS,
  NAV_GAP,
  navSpans,
  navVars,
  WORDMARK_COLS,
} from "@/lib/nav-layout";
import { gridGeometry } from "@/lib/grid-geometry";
import { measureText } from "@/lib/text-metrics";
import type { NavLayout, NavModel, NavPlacement, NavSpans } from "@/lib/types";

// Two placements overlap when they share a row and their column ranges meet.
function overlaps(ps: NavPlacement[]): boolean {
  return ps.some((a, i) =>
    ps.slice(i + 1).some(
      (b) => a.row === b.row && a.col < b.col + b.span && b.col < a.col + a.span,
    ),
  );
}

// Every visible item of a layout (the wordmark as placements too).
function items(nav: NavLayout, narrow: boolean): NavPlacement[] {
  const cols = narrow ? NARROW_WORDMARK_COLS : WORDMARK_COLS;
  const rows = narrow ? 2 : 3;
  const wordmark = Array.from({ length: rows }, (_, i) => ({ col: 1, span: cols, row: 1 + i }));
  return [
    ...wordmark,
    ...nav.tabs.filter((p): p is NavPlacement => !!p),
    ...(nav.more ? [nav.more] : []),
    ...nav.fixed,
    nav.city,
    ...nav.locales,
  ];
}

const spans = (over: Partial<NavSpans> = {}): NavSpans => ({
  genres: [3, 4, 2, 3, 2],
  tabbable: 5,
  topLevel: 5,
  active: -1,
  more: 3,
  activeMore: 0,
  fixed: [2, 3],
  city: 5,
  cityMenu: [4, 4, 4, 4, 4, 5],
  localeCount: 2,
  ...over,
});

// Rotterdam, nl, in navOrder: the top-level genres by volume (the last two
// under the weekly threshold), then the always-More ones — Kinderen, the
// busiest of all, and Folk; Film and Mijn lijst set apart.
const em = (s: string) => measureText(s).em;
const ROTTERDAM: NavModel = {
  genres: ["Dans", "Jazz", "Club", "Theater", "Pop", "Klassiek", "Alternatief", "Kinderen", "Folk"].map(em),
  tabbable: 5,
  topLevel: 7,
  active: -1,
  more: em("Meer"),
  fixed: [em("Film"), em("Mijn lijst")],
  city: em("Rotterdam"),
  cityMenu: ["Barcelona", "Yerevan", "Amsterdam", "Rotterdam", "Utrecht", "Alle steden"].map(em),
  localeCount: 2,
};

describe("flowLines", () => {
  it("flows items and right-aligns the fixed group on the last line after a gap", () => {
    const r = flowLines([3, 4], [2, 3], [{ row: 3, start: 12, end: 42 }])!;
    expect(r.flow).toEqual([
      { col: 12, span: 3, row: 3 },
      { col: 15, span: 4, row: 3 },
    ]);
    expect(r.fixed).toEqual([
      { col: 37, span: 2, row: 3 },
      { col: 39, span: 3, row: 3 },
    ]);
  });

  it("wraps onto the next line and keeps the gap before the fixed group", () => {
    const r = flowLines([4, 4, 4], [3], [
      { row: 3, start: 1, end: 10 },
      { row: 4, start: 1, end: 10 },
    ])!;
    expect(r.flow.map((p) => p.row)).toEqual([3, 3, 4]);
    expect(r.fixed).toEqual([{ col: 7, span: 3, row: 4 }]);
    expect(r.flow[2].col + r.flow[2].span + NAV_GAP).toBeLessThanOrEqual(r.fixed[0].col);
  });

  it("fails when the items don't fit", () => {
    expect(flowLines([5, 5], [3], [{ row: 3, start: 1, end: 12 }])).toBeNull();
  });
});

describe("fitTabs (the More split)", () => {
  const line = (end: number) => [{ row: 3, start: 1, end }];

  it("shows every tab, without More, when they fit", () => {
    const r = fitTabs(spans(), line(40))!;
    expect(r.k).toBe(5);
    expect(r.flow).toHaveLength(5); // no trigger
  });

  it("keeps genres under the weekly threshold in More even with room", () => {
    const r = fitTabs(spans({ tabbable: 3 }), line(40))!;
    expect(r.k).toBe(3);
    expect(r.flow).toHaveLength(4); // 3 tabs + More
  });

  it("moves the overflowing tail into More", () => {
    // 18 cells: fixed 5 + gap 1 → 12 for tabs + More (3).
    const r = fitTabs(spans(), line(19))!;
    expect(r.k).toBe(3); // 3 + 4 + 2 + More 3 = 12; a 4th tab (3) → 15
    const flowEnd = Math.max(...r.flow.map((p) => p.col + p.span));
    expect(flowEnd + NAV_GAP).toBeLessThanOrEqual(r.fixed[0].col);
  });

  it("never puts a single genre in More when its own tab fits", () => {
    // tabbable 4 of 5: More would hold one genre (span 2 ≤ More's 3).
    expect(fitTabs(spans({ tabbable: 4 }), line(40))!.k).toBe(5);
  });

  it("keeps a lone non-top-level genre in More even when its tab would fit", () => {
    // Genre 4 is not in TOP_LEVEL_GENRES (topLevel 4): More holds just it.
    const r = fitTabs(spans({ tabbable: 4, topLevel: 4 }), line(40))!;
    expect(r.k).toBe(4);
    expect(r.flow).toHaveLength(5); // 4 tabs + More
  });

  it("never gives a tab past the top-level run, however wide the bar", () => {
    const r = fitTabs(spans({ tabbable: 2, topLevel: 2 }), line(200))!;
    expect(r.k).toBe(2);
  });

  it("sizes the trigger for the active genre's name when it is in More", () => {
    // Active genre 4 (span 2) is in More: its trigger is 2 + 1 chevron.
    const r = fitTabs(spans({ tabbable: 2, active: 4, activeMore: 3, genres: [3, 4, 2, 3, 6] }), line(40))!;
    expect(r.k).toBe(2);
    const wide = fitTabs(spans({ tabbable: 2, active: 4, activeMore: 7, genres: [3, 4, 2, 3, 6] }), line(40))!;
    expect(wide.flow[2].span).toBe(7);
  });
});

describe("layoutNav", () => {
  it("desktop: tabs beside the wordmark on row 3, city · locales on row 1", () => {
    const nav = layoutNav(spans(), 41, false);
    expect(nav.tabs[0]).toEqual({ col: 1 + WORDMARK_COLS, span: 3, row: 3 });
    expect(nav.fixed.at(-1)!.col + nav.fixed.at(-1)!.span).toBe(42); // right-aligned
    expect(nav.locales).toEqual([
      { col: 40, span: 1, row: 1 },
      { col: 41, span: 1, row: 1 },
    ]);
    expect(nav.city).toEqual({ col: 40 - NAV_GAP - 5, span: 5, row: 1 });
    // Under the trigger (widest entry 5 + 1 cells), inside the band.
    expect(nav.cityMenu).toEqual({ col: nav.city.col, row: 1, width: 6 });
    expect(layoutNav(spans({ city: 3 }), 41, false).cityMenu.col).toBe(42 - 6);
  });

  it("desktop: moves the tabs below the wordmark when beside is too cramped", () => {
    // 23 cells: 12 beside → fixed 5 + gap + More 3 leaves 3 → one tab.
    const nav = layoutNav(spans(), 23, false);
    expect(nav.tabs[0]!.row).toBe(4);
    expect(nav.tabs.filter(Boolean).length).toBeGreaterThanOrEqual(MIN_BESIDE_TABS);
  });

  it("places the More menu under its trigger, inside the band", () => {
    const nav = layoutNav(spans({ tabbable: 2 }), 30, false);
    expect(nav.more).not.toBeNull();
    expect(nav.moreMenu!.row).toBe(nav.more!.row);
    expect(nav.moreMenu!.col + nav.moreMenu!.width).toBeLessThanOrEqual(31);
    expect(nav.moreMenu!.width).toBe(3 + 1); // widest entry (genres 2–4) + 1
  });

  it("narrow: city on row 1 and locales on row 2 when they don't share a row", () => {
    const nav = layoutNav(spans(), 16, true); // 7 cells beside the wordmark
    expect(nav.city).toEqual({ col: 17 - 5, span: 5, row: 1 });
    expect(nav.locales.map((p) => p.row)).toEqual([2, 2]);
    expect(nav.locales.at(-1)!.col).toBe(16);
  });

  it("narrow: city and locales share row 1 when there's room", () => {
    const nav = layoutNav(spans({ city: 4 }), 20, true); // 11 beside
    expect(nav.city.row).toBe(1);
    expect(nav.locales.every((p) => p.row === 1)).toBe(true);
    expect(nav.city.col + nav.city.span + NAV_GAP).toBe(nav.locales[0].col);
  });

  it("narrow: one tab row when everything fits, two at most", () => {
    expect(layoutNav(spans({ genres: [3, 2] }), 16, true).tabs.every((p) => p!.row === 3)).toBe(true);
    const nav = layoutNav(spans(), 16, true);
    const rows = [...nav.tabs, nav.more, ...nav.fixed].filter(Boolean).map((p) => p!.row);
    expect(Math.max(...rows)).toBeLessThanOrEqual(4);
  });

  it("never overlaps, at any width, in either layout", () => {
    for (const narrow of [false, true]) {
      for (let cells = narrow ? 13 : 20; cells <= 60; cells++) {
        for (const sp of [spans(), spans({ tabbable: 2, active: 3, activeMore: 4 }), spans({ genres: [] })]) {
          const nav = layoutNav(sp, cells, narrow);
          const all = items(nav, narrow);
          expect(overlaps(all), `cells=${cells} narrow=${narrow}`).toBe(false);
          expect(all.every((p) => p.col >= 1 && p.col + p.span <= cells + 1), `cells=${cells}`).toBe(true);
          // Film · My list keep their gap after the last tab / More.
          const flow = [...nav.tabs, nav.more].filter((p): p is NavPlacement => !!p);
          const last = flow.filter((p) => p.row === nav.fixed[0].row);
          for (const p of last) expect(p.col + p.span + NAV_GAP).toBeLessThanOrEqual(nav.fixed[0].col);
        }
      }
    }
  });
});

describe("navVars", () => {
  it("places items relative to --col-start, never on absolute lines", () => {
    const wide = navVars(ROTTERDAM, gridGeometry(1400, false), false);
    expect(wide["--t0c"]).toBe(String(WORDMARK_COLS));
    expect(wide["--t0r"]).toBe("3");
    // 2000px has a different --col-start but the same band.
    expect(navVars(ROTTERDAM, gridGeometry(2000, false), false)).toEqual(wide);
  });

  it("Rotterdam at 1400px: five tabs; the quiet two, then Kinderen and Folk, in More", () => {
    const v = navVars(ROTTERDAM, gridGeometry(1400, false), false);
    expect([0, 1, 2, 3, 4].map((i) => v[`--t${i}d`])).toEqual(Array(5).fill("flex"));
    expect([5, 6, 7, 8].map((i) => v[`--t${i}d`])).toEqual(Array(4).fill("none"));
    expect([5, 6, 7, 8].map((i) => [v[`--m${i}d`], v[`--m${i}r`]])).toEqual([
      ["flex", "1"],
      ["flex", "2"],
      ["flex", "3"],
      ["flex", "4"],
    ]);
    expect(v["--mmh"]).toBe("4");
    expect(v["--mtd"]).toBe("flex");
    expect(v["--mad"]).toBe("none");
  });

  it("shows the active genre on the More trigger when it's in More", () => {
    const v = navVars({ ...ROTTERDAM, active: 6 }, gridGeometry(1400, false), false);
    expect(v["--mtd"]).toBe("none");
    expect(v["--mad"]).toBe("flex");
    // "Alternatief" (5 cells at 32px) + the chevron.
    expect(Number(v["--mts"])).toBeGreaterThan(Number(navVars(ROTTERDAM, gridGeometry(1400, false), false)["--mts"]));
  });

  it("narrow 390px: fewer tabs, the tail in More, nothing past row 4", () => {
    const g = gridGeometry(390, true);
    const v = navVars(ROTTERDAM, g, true);
    const rows = Object.entries(v)
      .filter(([k]) => /^--(t\d+|f\d+|mt)r$/.test(k))
      .map(([, r]) => Number(r));
    expect(Math.max(...rows)).toBeLessThanOrEqual(4);
    expect(v["--l0r"]).toBe("2"); // locales below the city
    expect(v["--cr"]).toBe("1");
  });

  it("spans whole cells of the narrow cell at the exact width", () => {
    const m: NavModel = { ...ROTTERDAM, fixed: [em("Film"), em("My list")] };
    const s = (w: number) => navSpans(m, gridGeometry(w, true)).fixed[1];
    // 16px "My list" ≈ 45.2px + 7 → 3 cells of 24px …
    expect(s(384)).toBe(3);
    // … but 2 once the cell grows past 26.1px (8 cells over 215px).
    expect(s(215)).toBe(2);
  });
});
