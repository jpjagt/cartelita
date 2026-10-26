import { describe, it, expect } from "vitest";
import {
  countBucket,
  dayOffset,
  depthBucket,
  logicalToday,
  navEvent,
  pageOfPath,
  referrerSource,
} from "@/lib/analytics";

describe("logicalToday", () => {
  it("is the calendar date from 05:00", () => {
    expect(logicalToday(new Date(2026, 9, 14, 5, 0))).toBe("2026-10-14");
    expect(logicalToday(new Date(2026, 9, 14, 23, 59))).toBe("2026-10-14");
  });
  it("rolls back a day before 05:00 (across month ends too)", () => {
    expect(logicalToday(new Date(2026, 9, 14, 4, 59))).toBe("2026-10-13");
    expect(logicalToday(new Date(2026, 10, 1, 1, 0))).toBe("2026-10-31");
  });
});

describe("dayOffset", () => {
  it("counts whole days ahead", () => {
    expect(dayOffset("2026-10-14", "2026-10-14")).toBe(0);
    expect(dayOffset("2026-10-15", "2026-10-14")).toBe(1);
    expect(dayOffset("2026-11-02", "2026-10-30")).toBe(3);
  });
  it("is unaffected by DST changes", () => {
    expect(dayOffset("2026-10-26", "2026-10-24")).toBe(2);
  });
  it("is negative for a past day and 0 for garbage", () => {
    expect(dayOffset("2026-10-13", "2026-10-14")).toBe(-1);
    expect(dayOffset("", "2026-10-14")).toBe(0);
  });
});

describe("depthBucket", () => {
  it.each([
    [-1, "0"], [0, "0"], [1, "1"], [2, "2"], [3, "3-6"], [6, "3-6"],
    [7, "7-13"], [13, "7-13"], [14, "14-29"], [29, "14-29"], [30, "30+"], [90, "30+"],
  ])("%i → %s", (n, bucket) => expect(depthBucket(n)).toBe(bucket));
});

describe("countBucket", () => {
  it.each([[0, "0"], [1, "1"], [2, "2-4"], [4, "2-4"], [5, "5-9"], [10, "10+"]])(
    "%i → %s",
    (n, bucket) => expect(countBucket(n)).toBe(bucket),
  );
});

describe("referrerSource", () => {
  const own = "cartelita.co";
  it.each([
    ["", "direct"],
    ["https://cartelita.co/barcelona", "internal"],
    ["https://www.google.es/", "search"],
    ["https://duckduckgo.com/", "search"],
    ["https://l.instagram.com/", "social"],
    ["https://t.co/abc", "social"],
    ["https://web.whatsapp.com/", "social"],
    ["https://someblog.example/post", "other"],
    ["not a url", "other"],
  ])("%s → %s", (ref, source) => expect(referrerSource(ref, own)).toBe(source));
});

describe("pageOfPath", () => {
  it("reads city, locale and list", () => {
    expect(pageOfPath("/barcelona/es/club")).toEqual({ city: "barcelona", locale: "es", list: "club" });
    expect(pageOfPath("/amsterdam/en/my-list/")).toEqual({ city: "amsterdam", locale: "en", list: "my-list" });
  });
  it("fills the city's defaults for the bare city and locale pages", () => {
    expect(pageOfPath("/barcelona")).toEqual({ city: "barcelona", locale: "ca", list: "jazz" });
    expect(pageOfPath("/utrecht/en")).toEqual({ city: "utrecht", locale: "en", list: "pop" });
  });
  it("has no city for the picker or unknown paths", () => {
    expect(pageOfPath("/")).toEqual({ city: "", locale: "", list: "" });
    expect(pageOfPath("/nowhere/en/jazz")).toEqual({ city: "", locale: "", list: "" });
  });
});

describe("navEvent", () => {
  const p = (city: string, locale: string, list: string) => ({ city, locale, list });
  it("a tab change is nav_tab", () => {
    expect(navEvent(p("barcelona", "ca", "jazz"), p("barcelona", "ca", "club"), "tab")).toEqual({
      name: "nav_tab",
      data: { from_list: "jazz", to_list: "club", city: "barcelona", locale: "ca", via: "tab" },
    });
  });
  it("a locale change is locale_switch", () => {
    expect(navEvent(p("barcelona", "ca", "jazz"), p("barcelona", "en", "jazz"), "locale")).toEqual({
      name: "locale_switch",
      data: { from: "ca", to: "en", city: "barcelona", list: "jazz", via: "locale" },
    });
  });
  it("a city change is city_switch, even when locale and list change too", () => {
    expect(navEvent(p("", "", ""), p("amsterdam", "nl", "jazz"), "picker")).toEqual({
      name: "city_switch",
      data: { from: "none", to: "amsterdam", list: "jazz", via: "picker" },
    });
  });
  it("back to the picker is a city_switch to none", () => {
    expect(navEvent(p("barcelona", "ca", "jazz"), p("", "", ""), "city_menu")?.data).toEqual({
      from: "barcelona", to: "none", list: "", via: "city_menu",
    });
  });
  it("the same page is no event", () => {
    expect(navEvent(p("barcelona", "ca", "jazz"), p("barcelona", "ca", "jazz"), "logo")).toBeNull();
  });
});
