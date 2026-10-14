import { describe, it, expect } from "vitest";
import { cityConfig, cityHref, MY_LIST } from "@/lib/cities";

describe("cityHref", () => {
  const ams = cityConfig("amsterdam");
  const bcn = cityConfig("barcelona");

  it("keeps the locale and list when the target city has them", () => {
    expect(cityHref(ams, "en", "jazz", ["jazz", "club"])).toBe("/amsterdam/en/jazz");
  });

  it("falls back to the target's default locale", () => {
    expect(cityHref(bcn, "nl", "jazz", ["jazz"])).toBe("/barcelona/ca/jazz");
  });

  it("falls back to the target's default list", () => {
    expect(cityHref(ams, "nl", "flamenco", ["jazz", "club"])).toBe("/amsterdam/nl/jazz");
  });

  it("keeps My list everywhere", () => {
    expect(cityHref(bcn, "en", MY_LIST, [])).toBe("/barcelona/en/my-list");
  });
});
