import { describe, it, expect } from "vitest";
import { ogNav, placeNav, renderOgHtml, OG_NAV_ROW } from "@/lib/og-template";
import type { AgendaDay, CategoryList, OgNavItem } from "@/lib/types";

// London-ish: four genres busy enough for a tab, two thin ones, and film.
// (A tab needs ≥ 20 events in the 28-day nav window: lib/genre-nav.ts.)
const lists: CategoryList[] = [
  { slug: "theater", upcoming: 120 },
  { slug: "jazz", upcoming: 90 },
  { slug: "classical", upcoming: 60 },
  { slug: "pop", upcoming: 25 },
  { slug: "club", upcoming: 4 },
  { slug: "kids", upcoming: 30 },
  { slug: "film", upcoming: 400 },
];

describe("ogNav", () => {
  it("shows the city's own tabs in navbar order, then and more, then Today · Film · My list", () => {
    const nav = ogNav("en", "theater", lists);
    expect(nav.map((n) => n.label)).toEqual([
      "Theater", "Jazz", "Classical", "Pop", "and more", "Today", "Film", "My list",
    ]);
    expect(nav.filter((n) => n.fixed).map((n) => n.slug)).toEqual(["today", "film", "my-list"]);
  });

  it("marks the active list in place", () => {
    const nav = ogNav("es", "jazz", lists);
    expect(nav.filter((n) => n.active).map((n) => n.label)).toEqual(["Jazz"]);
    expect(nav[1].active).toBe(true);
  });

  it("names the classical list (slug `classical`) — it used to be dropped as `classic`", () => {
    expect(ogNav("ca", "classical", lists).map((n) => n.label)).toContain("Clàssica");
  });

  it("adds the active genre when it lives behind More", () => {
    const nav = ogNav("en", "club", lists);
    expect(nav.map((n) => n.label)).toEqual([
      "Theater", "Jazz", "Classical", "Pop", "Club", "and more", "Today", "Film", "My list",
    ]);
    expect(nav.find((n) => n.slug === "club")?.active).toBe(true);
  });

  it("marks Today / My list active on their pages", () => {
    expect(ogNav("en", "today", lists).find((n) => n.active)?.label).toBe("Today");
    expect(ogNav("nl", "my-list", lists).find((n) => n.active)?.label).toBe("Mijn lijst");
  });

  it("offers no Film tab in a city without a film list", () => {
    const nav = ogNav("nl", "jazz", lists.filter((l) => l.slug !== "film"));
    expect(nav.map((n) => n.slug)).not.toContain("film");
  });

  it("skips genres with nothing upcoming", () => {
    const nav = ogNav("en", "jazz", [{ slug: "jazz", upcoming: 3 }, { slug: "pop", upcoming: 0 }]);
    expect(nav.map((n) => n.label)).toEqual(["Jazz", "and more", "Today", "My list"]);
  });
});

describe("placeNav", () => {
  const item = (slug: string | null, fixed = false, active = false): OgNavItem => ({
    slug, label: slug ?? "and more", active, fixed,
  });

  it("flows genres from column 1 and sets the fixed tabs flush right", () => {
    const items = [item("jazz", false, true), item("pop"), item(null), item("today", true), item("my-list", true)];
    expect(placeNav(items, [2, 2, 3, 2, 3], 26)).toEqual([1, 3, 5, 22, 24]);
  });

  it("drops inactive genres from the end when the band overflows", () => {
    const items = [item("theater"), item("jazz", false, true), item("pop"), item("rock"), item(null), item("today", true)];
    // 4+4+4+4+3 genres + 1 gap + 4 fixed = 24 > 20: rock goes (20 fits);
    // in 16 columns pop goes too.
    expect(placeNav(items, [4, 4, 4, 4, 3, 4], 20)).toEqual([1, 5, 9, null, 13, 17]);
    expect(placeNav(items, [4, 4, 4, 4, 3, 4], 16)).toEqual([1, 5, null, null, 9, 13]);
  });

  it("never drops the active genre or and more", () => {
    const items = [item("jazz", false, true), item(null), item("today", true)];
    expect(placeNav(items, [10, 10, 10], 20)).toEqual([1, 11, 11]);
  });
});

describe("renderOgHtml", () => {
  const days: AgendaDay[] = [
    {
      date: "2026-06-07",
      events: [
        {
          id: 1, title: "Martin Harley", startDate: "2026-06-07",
          startTime: "19:00", venueSlug: "jamboree", venueName: "Jamboree", price: "16€",
          sourceUrl: "https://x", recurrenceHint: null, language: null, description: null,
        },
      ],
    },
  ];
  const nav = ogNav("es", "jazz", lists);
  const html = renderOgHtml({ locale: "es", city: "Barcelona", nav, body: { kind: "agenda", days } });

  it("renders a full HTML document with fixed 1200x630 canvas", () => {
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("width:1200px");
    expect(html).toContain("height:630px");
    expect(html).toContain("repeat(26");
    expect(html).toContain('<html lang="es">');
  });

  it("puts the city beside the wordmark, on its three rows", () => {
    expect(html).toContain("telita</span>");
    expect(html).toContain('<span class="city-text">Barcelona</span>');
    expect(html).toMatch(/\.wordmark, \.city \{\s*grid-row:1 \/ span 3/);
    expect(renderOgHtml({ locale: "hy", city: "Երևան", nav: [], body: { kind: "agenda", days: [] } }))
      .toContain("Երևան");
  });

  it("emits one nav cell per entry on the nav row, placed by scripts/og.ts", () => {
    // Each item is its own grid cell (whole cells fitting its text, like the
    // live navbar); og.ts measures the labels and assigns the columns
    // (placeNav), so the template carries only the row.
    const items = [...html.matchAll(/class="cell navitem" data-navitem style="grid-row:(\d+);/g)];
    expect(items.length).toBe(nav.length);
    expect(items.every((m) => Number(m[1]) === OG_NAV_ROW)).toBe(true);
    expect(html).toContain("Teatro");
    expect(html).toContain("y más");
    expect(html).toContain("Mi lista");
    // No locale switcher.
    expect(html).not.toContain(">CA<");
    expect(html).not.toContain(">EN<");
  });

  it("fills the active tab with its genre colour, or the foreground for pages without one", () => {
    expect(html).toContain('background:#d3000e;color:#ffffff;"><span class="t">Jazz</span>');
    const today = renderOgHtml({ locale: "en", city: "London", nav: ogNav("en", "today", lists), body: { kind: "agenda", days } });
    expect(today).toContain('background:oklch(0.145 0 0);color:oklch(1 0 0);"><span class="t">Today</span>');
  });

  it("renders the event row fields with OG column spans", () => {
    expect(html).toContain("Martin Harley");
    expect(html).toContain("Jamboree");
    expect(html).toContain("16€");
    expect(html).toContain("19:00");
    expect(html).toContain("grid-column:-9/span 6"); // venue
    expect(html).toContain("grid-column:-3/span 2"); // price
    expect(html).toContain("grid-column:1/span 2");  // time
    expect(html).toContain("grid-column:3/-9");      // title fills slack
  });

  it("renders the localized day heading", () => {
    expect(html.toLowerCase()).toContain("domingo, 7 de junio");
  });

  it("escapes text", () => {
    const out = renderOgHtml({ locale: "en", city: "A<b>", nav: [], body: { kind: "cities", heading: "x", cities: ["R&B"] } });
    expect(out).toContain("A&lt;b&gt;");
    expect(out).toContain("R&amp;B");
  });

  it("renders the empty state when there are no days", () => {
    const out = renderOgHtml({ locale: "en", city: "London", nav: [], body: { kind: "agenda", days: [] } });
    expect(out).toContain("No upcoming events.");
  });

  it("renders the venue directory (My list) and the city list (picker)", () => {
    const venues = renderOgHtml({
      locale: "en", city: "London", nav: [],
      body: { kind: "venues", heading: "Mark your favourite venues", venues: ["Cafe OTO", "Barbican"] },
    });
    expect(venues).toContain("Mark your favourite venues");
    expect(venues).toContain("Cafe OTO");
    const picker = renderOgHtml({
      locale: "en", nav: [], body: { kind: "cities", heading: "what's on", cities: ["Barcelona", "London"] },
    });
    expect(picker).toContain("What's on"); // capitalised heading
    expect(picker).toContain("London");
    expect(picker).not.toContain("data-city");
  });
});
