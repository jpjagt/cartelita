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

  it("keeps the fixed order jazz·theater·classic·film, then andMore", () => {
    const nav = ogGenreNav("es", "jazz", lists);
    expect(nav.map((n) => n.label)).toEqual([
      "Jazz", "Teatro", "Clásica", "Cine", "y más",
    ]);
    // The active list keeps its fill in place; it is NOT hoisted to the front.
    expect(nav[0].active).toBe(true); // jazz is first in the fixed order anyway
  });

  it("marks the active genre in place without reordering", () => {
    const nav = ogGenreNav("en", "theater", lists);
    expect(nav.map((n) => n.label)).toEqual([
      "Jazz", "Theater", "Classical", "Film", "and more",
    ]);
    // Theater stays in its fixed slot (index 1) and is the active one.
    expect(nav.map((n) => n.active)).toEqual([false, true, false, false, false]);
  });

  it("appends the active genre as the [x] slot when it is not one of the fixed four", () => {
    const nav = ogGenreNav("es", "pop", lists);
    // Fixed four first, then pop (the active 'other' genre), then andMore.
    expect(nav.map((n) => n.label)).toEqual([
      "Jazz", "Teatro", "Clásica", "Cine", "Pop", "y más",
    ]);
    const pop = nav.find((n) => n.slug === "pop");
    expect(pop?.active).toBe(true);
  });

  it("skips fixed slugs that are not real DB lists", () => {
    const nav = ogGenreNav("en", "jazz", ["jazz", "classic"]);
    // theater + film dropped (not in lists); jazz + classic kept, in order.
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

  it("uses the light theme (white background, near-black foreground)", () => {
    const html = renderOgHtml({ locale: "es", list: "jazz", lists, days });
    expect(html).toContain("background:oklch(1 0 0)"); // white page
    expect(html).not.toContain("oklch(0.145 0 0)100%"); // sanity: no concat glitch
    // The wordmark spans three rows (matching the live site).
    expect(html).toContain("grid-row:1 / span 3");
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

  it("lays the genre nav out as one flex cell after the wordmark", () => {
    const html = renderOgHtml({ locale: "es", list: "jazz", lists, days });
    // The nav is a SINGLE grid cell spanning cols 12→end on row 3 (the
    // wordmark's baseline row; the wordmark is 3 rows tall and 11 cols wide), so
    // it can never overflow the 26-col canvas the way per-item columns did, and
    // it flexes its items. Exactly one nav container and one .navitem per nav
    // entry (Jazz + Teatro + Clásica + Cine + y más = 5).
    expect(html).toContain('class="cell nav" style="grid-row:3;grid-column:12/-1;"');
    const items = [...html.matchAll(/class="navitem"/g)];
    expect(items.length).toBe(5);
    // No leftover per-item grid-column placement on the nav row.
    expect(html).not.toMatch(/grid-row:3;grid-column:\d+\/span/);
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
