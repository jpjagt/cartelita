import { describe, it, expect } from "vitest";
import {
  earnsTab,
  isTopLevel,
  MORE_THRESHOLD_PER_WEEK,
  NAV_WINDOW_DAYS,
  navOrder,
  orderByVolume,
  tabbableCount,
  TOP_LEVEL_GENRES,
  topLevelCount,
} from "@/lib/genre-nav";

const l = (slug: string, upcoming: number) => ({ slug, upcoming });
// The weekly threshold over the window, in events.
const AT = (MORE_THRESHOLD_PER_WEEK * NAV_WINDOW_DAYS) / 7;

describe("orderByVolume", () => {
  it("puts the busiest list first", () => {
    expect(orderByVolume([l("jazz", 53), l("kids", 123), l("dance", 68)]).map((x) => x.slug)).toEqual([
      "kids",
      "dance",
      "jazz",
    ]);
  });

  it("breaks ties alphabetically by slug, whatever the input order", () => {
    const a = orderByVolume([l("pop", 17), l("alternative", 17), l("classical", 17)]);
    const b = orderByVolume([l("classical", 17), l("pop", 17), l("alternative", 17)]);
    expect(a.map((x) => x.slug)).toEqual(["alternative", "classical", "pop"]);
    expect(b).toEqual(a);
  });

  it("does not mutate its input", () => {
    const input = [l("a", 1), l("b", 2)];
    orderByVolume(input);
    expect(input.map((x) => x.slug)).toEqual(["a", "b"]);
  });
});

describe("TOP_LEVEL_GENRES / navOrder", () => {
  it("allows exactly the eight top-level genres", () => {
    expect([...TOP_LEVEL_GENRES].sort()).toEqual(
      ["alternative", "classical", "club", "dance", "jazz", "pop", "rock", "theater"],
    );
    for (const slug of ["kids", "folk", "flamenco", "something-new"]) expect(isTopLevel(l(slug, 999))).toBe(false);
  });

  it("puts the top-level genres first by volume, then the rest by volume", () => {
    // Rotterdam-like: kids is the busiest of all but still goes last-but-one.
    const r = navOrder([l("folk", 4), l("jazz", 53), l("kids", 123), l("pop", 9), l("dance", 68), l("flamenco", 7)]);
    expect(r.map((x) => x.slug)).toEqual(["dance", "jazz", "pop", "kids", "flamenco", "folk"]);
    expect(topLevelCount(r)).toBe(3);
  });
});

describe("tabbableCount", () => {
  it("counts the leading run at or above the weekly threshold", () => {
    expect(earnsTab(l("x", AT))).toBe(true);
    expect(earnsTab(l("x", AT - 1))).toBe(false);
    expect(tabbableCount([l("jazz", 100), l("club", AT), l("pop", AT - 1), l("rock", 2)])).toBe(2);
  });

  it("stops at the first genre that's not top-level, however busy", () => {
    expect(tabbableCount(navOrder([l("kids", 500), l("jazz", 100), l("flamenco", 300)]))).toBe(1);
  });

  it("still gives the busiest top-level genre a tab when none clears the bar", () => {
    expect(tabbableCount([l("jazz", 3), l("pop", 1)])).toBe(1);
    expect(tabbableCount(navOrder([l("kids", 100), l("rock", 3)]))).toBe(1);
  });

  it("gives no tab when there's no top-level genre with events", () => {
    expect(tabbableCount([l("jazz", 0), l("pop", 0)])).toBe(0);
    expect(tabbableCount([l("kids", 100), l("folk", 50)])).toBe(0);
    expect(tabbableCount([])).toBe(0);
  });
});
