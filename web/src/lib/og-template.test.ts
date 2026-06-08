import { describe, it, expect } from "vitest";
import { ogGenreNav, slugForName } from "@/lib/og-template";

describe("slugForName", () => {
  it("maps classic to the classical i18n key", () => {
    expect(slugForName("classic")).toBe("classical");
  });
  it("leaves other slugs unchanged", () => {
    expect(slugForName("jazz")).toBe("jazz");
  });
});

describe("ogGenreNav", () => {
  const lists = ["jazz", "classic", "theater", "film", "club", "pop"];

  it("puts the active genre first, then the fixed four minus active, then andMore", () => {
    const nav = ogGenreNav("es", "jazz", lists);
    expect(nav.map((n) => n.label)).toEqual([
      "Jazz", "Clásica", "Teatro", "Cine", "y más",
    ]);
    expect(nav[0].active).toBe(true);
    expect(nav.slice(1).every((n) => !n.active)).toBe(true);
  });

  it("does not duplicate the active genre when it is one of the fixed four", () => {
    const nav = ogGenreNav("en", "theater", lists);
    expect(nav.map((n) => n.label)).toEqual([
      "Theater", "Jazz", "Classical", "Film", "and more",
    ]);
  });

  it("skips fixed slugs that are not real DB lists", () => {
    const nav = ogGenreNav("en", "jazz", ["jazz", "classic"]);
    // film + theater dropped (not in lists); classic kept
    expect(nav.map((n) => n.label)).toEqual(["Jazz", "Classical", "and more"]);
  });

  it("carries the genre slug for color styling", () => {
    const nav = ogGenreNav("en", "jazz", lists);
    expect(nav[0].slug).toBe("jazz");
  });
});
