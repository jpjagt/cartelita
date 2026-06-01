import { describe, it, expect } from "vitest";
import { groupEventsByDay } from "@/lib/agenda";
import type { AgendaEvent } from "@/lib/types";

const ev = (id: number, date: string): AgendaEvent => ({
  id, title: `E${id}`, startDate: date, startTime: null,
  venueName: "Jamboree", price: null, sourceUrl: "https://x", recurrenceHint: null,
});

describe("groupEventsByDay", () => {
  it("buckets events by date, preserving order", () => {
    const days = groupEventsByDay([ev(1, "2026-06-02"), ev(2, "2026-06-02"), ev(3, "2026-06-09")]);
    expect(days.map((d) => d.date)).toEqual(["2026-06-02", "2026-06-09"]);
    expect(days[0].events.map((e) => e.id)).toEqual([1, 2]);
    expect(days[1].events.map((e) => e.id)).toEqual([3]);
  });

  it("returns empty array for no events", () => {
    expect(groupEventsByDay([])).toEqual([]);
  });
});
