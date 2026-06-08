import { describe, it, expect } from "vitest";
import { groupFilmDay } from "@/lib/film-agenda";
import type { AgendaEvent } from "@/lib/types";

const ev = (
  id: number,
  title: string,
  startTime: string | null,
  venue = "Renoir",
): AgendaEvent => ({
  id,
  title,
  startDate: "2026-06-08",
  startTime,
  venueName: venue,
  price: "8,50€",
  sourceUrl: `https://x/${id}`,
  recurrenceHint: null,
});

describe("groupFilmDay", () => {
  it("groups events by title, one card per film", () => {
    const layout = groupFilmDay("2026-06-08", [
      ev(1, "BACKROOMS", "16:00"),
      ev(2, "BACKROOMS", "20:30"),
      ev(3, "LA LUZ", "18:05"),
    ]);
    expect(layout.films.map((p) => p.film.title)).toEqual(["BACKROOMS", "LA LUZ"]);
    expect(layout.films[0].film.showtimes.map((s) => s.id)).toEqual([1, 2]);
  });

  it("groups title variants that differ only in case or bracket suffix", () => {
    const layout = groupFilmDay("2026-06-08", [
      ev(1, "El Drama (VOSE)", "16:00"),
      ev(2, "EL DRAMA", "20:30"),
    ]);
    expect(layout.films).toHaveLength(1);
    expect(layout.films[0].film.showtimes.map((s) => s.id)).toEqual([1, 2]);
  });

  it("displays the variant with the fewest capitals, bracket suffix stripped", () => {
    const layout = groupFilmDay("2026-06-08", [
      ev(1, "El Drama (VOSE)", "16:00"),
      ev(2, "EL DRAMA", "20:30"),
    ]);
    expect(layout.films[0].film.title).toBe("El Drama");
  });

  it("keeps a single unique variation as-is (brackets included)", () => {
    const layout = groupFilmDay("2026-06-08", [
      ev(1, "LA LUZ [VOSE]", "18:05"),
    ]);
    expect(layout.films[0].film.title).toBe("LA LUZ [VOSE]");
  });

  it("keeps the brackets when every variant shares them, fewest-caps casing", () => {
    const layout = groupFilmDay("2026-06-08", [
      ev(1, "The Life of (Brian)", "16:00"),
      ev(2, "THE LIFE OF (BRIAN)", "20:30"),
    ]);
    expect(layout.films).toHaveLength(1);
    expect(layout.films[0].film.title).toBe("The Life of (Brian)");
  });

  it("sorts showtimes within a film by time", () => {
    const layout = groupFilmDay("2026-06-08", [
      ev(1, "LA LUZ", "20:25"),
      ev(2, "LA LUZ", "15:50"),
      ev(3, "LA LUZ", "18:05"),
    ]);
    expect(layout.films[0].film.showtimes.map((s) => s.startTime)).toEqual([
      "15:50",
      "18:05",
      "20:25",
    ]);
  });

  it("orders films by earliest showtime, left-to-right", () => {
    const layout = groupFilmDay("2026-06-08", [
      ev(1, "LATE", "22:00"),
      ev(2, "EARLY", "15:50"),
      ev(3, "MID", "18:00"),
    ]);
    expect(layout.films.map((p) => p.film.title)).toEqual(["EARLY", "MID", "LATE"]);
  });

  it("card height is 1 + showtime count", () => {
    const layout = groupFilmDay("2026-06-08", [
      ev(1, "A", "16:00"),
      ev(2, "A", "18:00"),
      ev(3, "A", "20:00"),
    ]);
    expect(layout.films[0].height).toBe(4);
  });

  it("records the latest showtime time for collapse", () => {
    const layout = groupFilmDay("2026-06-08", [
      ev(1, "A", "16:00"),
      ev(2, "A", "20:30"),
    ]);
    expect(layout.films[0].film.latestTime).toBe("20:30");
  });

  it("packs into the shortest column (3-col), preserving order on ties", () => {
    // Four single-showtime films; with 3 columns the first three fill cols
    // 0,1,2 at row 0, and the fourth lands in the shortest column (col 0,
    // leftmost on a tie) at the row below the first card + gutter.
    const layout = groupFilmDay("2026-06-08", [
      ev(1, "A", "15:00"),
      ev(2, "B", "16:00"),
      ev(3, "C", "17:00"),
      ev(4, "D", "18:00"),
    ]);
    const byTitle = Object.fromEntries(layout.films.map((p) => [p.film.title, p]));
    expect([byTitle.A.col3, byTitle.A.row3]).toEqual([0, 0]);
    expect([byTitle.B.col3, byTitle.B.row3]).toEqual([1, 0]);
    expect([byTitle.C.col3, byTitle.C.row3]).toEqual([2, 0]);
    // card A is height 2 (1 title + 1 showtime), + 1 gutter = next free row 3.
    expect([byTitle.D.col3, byTitle.D.row3]).toEqual([0, 3]);
  });

  it("packs a tall card so a later short card overtakes it (balance)", () => {
    // A has 3 showtimes (height 4); B,C have 1 (height 2). With 3 columns all
    // three start at row 0 in cols 0,1,2. The 2-col packing must put the tall
    // card and balance the rest.
    const layout = groupFilmDay("2026-06-08", [
      ev(1, "A", "15:00"),
      ev(2, "A", "15:30"),
      ev(3, "A", "16:00"),
      ev(10, "B", "17:00"),
      ev(20, "C", "18:00"),
    ]);
    const byTitle = Object.fromEntries(layout.films.map((p) => [p.film.title, p]));
    // 2-col: A(h4)->col0 row0; B(h2)->col1 row0; C(h2)-> shortest is col1
    // (height 3) vs col0 (height 5) -> col1, row 3.
    expect([byTitle.A.col2, byTitle.A.row2]).toEqual([0, 0]);
    expect([byTitle.B.col2, byTitle.B.row2]).toEqual([1, 0]);
    expect([byTitle.C.col2, byTitle.C.row2]).toEqual([1, 3]);
  });

  it("stacks single-column (mobile) sequentially, 2 rows per showtime", () => {
    // A: 2 showtimes -> 1 title + 2*2 = 5 rows; B starts after A + 1 gutter.
    const layout = groupFilmDay("2026-06-08", [
      ev(1, "A", "15:00"),
      ev(2, "A", "16:00"),
      ev(3, "B", "17:00"),
    ]);
    const byTitle = Object.fromEntries(layout.films.map((p) => [p.film.title, p]));
    expect(byTitle.A.row1).toBe(0);
    expect(byTitle.B.row1).toBe(6); // 1 title + 4 showtime rows + 1 gutter
  });

  it("reports total rows for each packing", () => {
    const layout = groupFilmDay("2026-06-08", [
      ev(1, "A", "15:00"),
      ev(2, "B", "16:00"),
    ]);
    // Two height-2 cards. 3-col: each in own column, max height 2. 2-col: same.
    // 1-col: A (1 title + 2 rows) + gutter + B (3 rows) = 3 + 1 + 3 = 7.
    expect(layout.rows3).toBe(2);
    expect(layout.rows2).toBe(2);
    expect(layout.rows1).toBe(7);
  });

  it("returns empty films for no events", () => {
    expect(groupFilmDay("2026-06-08", []).films).toEqual([]);
  });
});
