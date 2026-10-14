import { describe, it, expect } from "vitest";
import { earnsTab, MORE_THRESHOLD_PER_WEEK, NAV_WINDOW_DAYS, orderByVolume, tabbableCount } from "@/lib/genre-nav";

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

describe("tabbableCount", () => {
  it("counts the leading run at or above the weekly threshold", () => {
    expect(earnsTab(l("x", AT))).toBe(true);
    expect(earnsTab(l("x", AT - 1))).toBe(false);
    expect(tabbableCount([l("a", 100), l("b", AT), l("c", AT - 1), l("d", 2)])).toBe(2);
  });

  it("still gives the busiest genre a tab when none clears the bar", () => {
    expect(tabbableCount([l("a", 3), l("b", 1)])).toBe(1);
  });

  it("gives no tab to a city whose genres are all empty", () => {
    expect(tabbableCount([l("a", 0), l("b", 0)])).toBe(0);
    expect(tabbableCount([])).toBe(0);
  });
});
