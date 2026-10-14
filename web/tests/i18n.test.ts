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

  it("serves the Amsterdam locale", () => {
    expect(t("nl").myList).toBe("Mijn lijst");
    expect(categoryName("nl", "classical")).toBe("Klassiek");
    expect(localeTag("nl")).toBe("nl-NL");
  });

  it("serves the Yerevan locales", () => {
    expect(categoryName("hy", "jazz")).toBe("Ջազ");
    expect(categoryName("ru", "film")).toBe("Кино");
    expect(localeTag("hy")).toBe("hy-AM");
    expect(localeTag("ru")).toBe("ru-RU");
  });

  it("every locale translates every seeded category", () => {
    const locales = ["ca", "es", "en", "hy", "ru", "nl"] as const;
    // Mirror of scraper seed.CATEGORIES — a category a scraper can emit must
    // have a display name in every locale's chrome.
    const slugs = ["film", "jazz", "classical", "theater", "club", "flamenco",
                   "dance", "kids", "pop", "folk", "rock", "alternative"];
    for (const locale of locales) {
      for (const slug of slugs) {
        expect(categoryName(locale, slug), `${locale}/${slug}`).not.toBe(slug);
      }
      expect(t(locale).prices["free"]).toBeTruthy();
      expect(t(locale).prices["sold-out"]).toBeTruthy();
    }
  });

  it("every locale labels the navbar dropdowns and collapsed days", () => {
    for (const locale of ["ca", "es", "en", "hy", "ru", "nl"] as const) {
      const s = t(locale);
      for (const key of ["more", "city", "allCities", "eventsHidden"] as const) {
        expect(s[key], `${locale}.${key}`).toBeTruthy();
      }
    }
    expect(t("nl").more).toBe("Meer");
  });
});
