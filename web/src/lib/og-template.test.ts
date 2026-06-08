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

import { renderOgHtml } from "@/lib/og-template";
import type { AgendaDay } from "@/lib/types";

describe("renderOgHtml", () => {
  const lists = ["jazz", "classic", "theater", "film"];
  const days: AgendaDay[] = [
    {
      date: "2026-06-07",
      events: [
        {
          id: 1, title: "Martin Harley", startDate: "2026-06-07",
          startTime: "19:00", venueName: "Jamboree", price: "16€",
          sourceUrl: "https://x", recurrenceHint: null,
        },
      ],
    },
  ];

  it("renders a full HTML document with fixed 1200x630 canvas", () => {
    const html = renderOgHtml({ locale: "es", list: "jazz", lists, days });
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("width:1200px");
    expect(html).toContain("height:630px");
    expect(html).toContain("repeat(26");
  });

  it("includes the wordmark and the genre nav labels but no locale switcher", () => {
    const html = renderOgHtml({ locale: "es", list: "jazz", lists, days });
    expect(html).toContain("Ca"); // wordmark "Cartelita"
    expect(html).toContain("Teatro");
    expect(html).toContain("y más");
    // locale switcher tokens must NOT be present
    expect(html).not.toContain(">CA<");
    expect(html).not.toContain(">EN<");
  });

  it("renders the event row fields with OG column spans", () => {
    const html = renderOgHtml({ locale: "es", list: "jazz", lists, days });
    expect(html).toContain("Martin Harley");
    expect(html).toContain("Jamboree");
    expect(html).toContain("16€");
    expect(html).toContain("19:00");
    // right-anchored spans (negative line numbers) for venue + price
    expect(html).toContain("grid-column:-9/span 6"); // venue
    expect(html).toContain("grid-column:-3/span 2"); // price
    expect(html).toContain("grid-column:1/span 2");  // time
    expect(html).toContain("grid-column:3/-9");      // title fills slack
  });

  it("renders the localized day heading", () => {
    const html = renderOgHtml({ locale: "es", list: "jazz", lists, days });
    // es-ES long date for 2026-06-07
    expect(html.toLowerCase()).toContain("junio");
  });

  it("renders the empty state when there are no days", () => {
    const html = renderOgHtml({ locale: "en", list: "jazz", lists, days: [] });
    expect(html).toContain("No upcoming events.");
  });
});
