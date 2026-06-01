import { describe, it, expect } from "vitest";
import { t, categoryName, localeTag } from "@/i18n";

describe("i18n", () => {
  it("translates category names per locale", () => {
    expect(categoryName("es", "film")).toBe("Cine");
    expect(categoryName("ca", "film")).toBe("Cinema");
    expect(categoryName("en", "film")).toBe("Film");
  });

  it("falls back to slug for unknown category", () => {
    expect(categoryName("en", "opera")).toBe("opera");
  });

  it("provides locale-specific chrome and date tags", () => {
    expect(t("es").noEvents).toContain("eventos");
    expect(localeTag("ca")).toBe("ca-ES");
  });
});
