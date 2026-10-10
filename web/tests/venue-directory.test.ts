import { describe, it, expect } from "vitest";
import { layoutVenueDirectory } from "@/lib/venue-directory";
import { packCards } from "@/lib/masonry";

const venues = (n: number) =>
  Array.from({ length: n }, (_, i) => ({ slug: `v${i}`, name: `Venue ${i}` }));

describe("packCards", () => {
  it("places cards in the shortest column, leftmost on ties", () => {
    // heights 3, 1, 1, 1 over 3 columns: first row fills cols 0..2, the 4th
    // card goes under the shortest (col 1, height 1 + gutter = 2).
    const layout = packCards([3, 1, 1, 1]);
    expect(layout.placements.map((p) => [p.col3, p.row3])).toEqual([
      [0, 0], [1, 0], [2, 0], [1, 2],
    ]);
    expect(layout.rows3).toBe(3);
    expect(layout.rows1).toBe(3 + 1 + 1 + 1 + 3); // 4 cards + 3 gutters
  });

  it("consumes no rows for no cards", () => {
    expect(packCards([])).toEqual({ placements: [], rows3: 0, rows2: 0, rows1: 0 });
  });
});

describe("layoutVenueDirectory", () => {
  it("drops empty lists and sizes cards as title + one row per venue", () => {
    const layout = layoutVenueDirectory([
      { listSlug: "jazz", venues: venues(2) },
      { listSlug: "pop", venues: [] },
      { listSlug: "film", venues: venues(4) },
    ]);
    expect(layout.groups.map((g) => g.group.listSlug)).toEqual(["jazz", "film"]);
    expect(layout.rows3).toBe(5); // the film card: 1 title + 4 venues
    expect(layout.groups[1].row1).toBe(4); // jazz card (3 rows) + 1 gutter
  });
});
