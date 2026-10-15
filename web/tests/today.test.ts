import { describe, it, expect } from "vitest";
import {
  addDays,
  agendaClock,
  cityToday,
  effectiveSelection,
  isRemaining,
  mapVenues,
  matchesGenres,
  offeredGenres,
  readGenreSelection,
  rowEnd,
  wallClock,
  wallMinutes,
  writeGenreSelection,
} from "@/lib/today";
import type { RemainingInput, TodayEventMeta, TodayVenue } from "@/types/today";

function memoryStore(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
  };
}

const row = (over: Partial<RemainingInput> = {}): RemainingInput => ({
  date: "2026-10-15",
  time: "20:00",
  endDate: null,
  endTime: null,
  multi: false,
  ...over,
});

describe("today in the city's time zone", () => {
  // 2026-10-15 22:30 UTC = 00:30 on the 16th in Amsterdam (CEST, UTC+2),
  // 19:30 on the 15th in Asunción (UTC−3), 02:30 on the 16th in Yerevan.
  const instant = new Date("2026-10-15T22:30:00Z");

  it("reads the wall clock in the given zone", () => {
    expect(wallClock(instant, "Europe/Amsterdam")).toEqual({ date: "2026-10-16", time: "00:30" });
    expect(wallClock(instant, "America/Asuncion")).toEqual({ date: "2026-10-15", time: "19:30" });
  });

  it("counts before 05:00 as the evening before", () => {
    expect(cityToday(instant, "Europe/Amsterdam")).toBe("2026-10-15");
    expect(cityToday(instant, "Asia/Yerevan")).toBe("2026-10-15");
    expect(cityToday(new Date("2026-10-16T03:00:00Z"), "Europe/Amsterdam")).toBe("2026-10-16");
  });

  it("is independent of the browser's own zone", () => {
    // Midday UTC on the 15th is the 15th everywhere these cities are.
    for (const tz of ["Europe/Madrid", "Asia/Yerevan", "America/Asuncion"]) {
      expect(cityToday(new Date("2026-10-15T12:00:00Z"), tz)).toBe("2026-10-15");
    }
  });

  it("falls back to the browser's zone for an unknown zone", () => {
    expect(wallClock(instant, "Not/AZone")).toEqual(wallClock(instant));
  });

  it("builds syncAgenda's clock on the city's wall clock", () => {
    const c = agendaClock(new Date("2026-10-15T19:15:00Z"), "Europe/Amsterdam");
    expect(c).toEqual({ logicalDate: "2026-10-15", nowKey: "121:15", cutoffKey: "119:15" });
    // After midnight: post-midnight keys sort last.
    expect(agendaClock(instant, "Europe/Amsterdam").nowKey).toBe("200:30");
  });

  it("adds days across month ends", () => {
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  });
});

describe("remaining today: the end / 2h rule", () => {
  const at = (date: string, time: string) => ({ date, time });

  it("keeps events without a start time all day", () => {
    expect(rowEnd(row({ time: null }))).toBeNull();
    expect(isRemaining(row({ time: null }), at("2026-10-16", "04:59"))).toBe(true);
  });

  it("drops an event without an end two hours after it started", () => {
    expect(isRemaining(row(), at("2026-10-15", "19:00"))).toBe(true);
    expect(isRemaining(row(), at("2026-10-15", "21:59"))).toBe(true);
    expect(isRemaining(row(), at("2026-10-15", "22:00"))).toBe(false);
  });

  it("uses a known end instead", () => {
    const short = row({ endTime: "21:00" });
    expect(isRemaining(short, at("2026-10-15", "20:59"))).toBe(true);
    expect(isRemaining(short, at("2026-10-15", "21:00"))).toBe(false);
    const long = row({ time: "12:00", endTime: "23:00" });
    expect(isRemaining(long, at("2026-10-15", "22:30"))).toBe(true);
  });

  it("rolls an end time before the start to the next day (club nights)", () => {
    const club = row({ time: "23:00", endTime: "05:00" });
    expect(wallMinutes("2026-10-16", "05:00") - (rowEnd(club) ?? 0)).toBe(0);
    expect(isRemaining(club, at("2026-10-16", "03:00"))).toBe(true);
  });

  it("honours an explicit end date with an end time", () => {
    const e = row({ time: "22:00", endDate: "2026-10-16", endTime: "06:00" });
    expect(isRemaining(e, at("2026-10-16", "05:30"))).toBe(true);
    expect(isRemaining(e, at("2026-10-16", "06:00"))).toBe(false);
  });

  it("keeps a multi-day run (end date, no end time) through the day", () => {
    const run = row({ time: "10:00", endDate: "2026-10-20" });
    expect(isRemaining(run, at("2026-10-15", "23:30"))).toBe(true);
  });

  it("treats each screening of a multi-showtime event on its own", () => {
    // The event's end would be 21:30, but each showtime gets start + 2h.
    const early = row({ time: "16:00", endTime: "21:30", multi: true });
    const late = row({ time: "21:00", endTime: "21:30", multi: true });
    const now = at("2026-10-15", "19:00");
    expect(isRemaining(early, now)).toBe(false);
    expect(isRemaining(late, now)).toBe(true);
  });

  it("handles post-midnight starts on their real date", () => {
    const late = row({ date: "2026-10-16", time: "01:00" });
    expect(isRemaining(late, at("2026-10-15", "23:00"))).toBe(true);
    expect(isRemaining(late, at("2026-10-16", "02:59"))).toBe(true);
    expect(isRemaining(late, at("2026-10-16", "03:00"))).toBe(false);
  });
});

describe("genre filter", () => {
  it("shows everything with nothing selected", () => {
    expect(matchesGenres(["jazz"], [])).toBe(true);
  });

  it("shows events in any selected genre", () => {
    expect(matchesGenres(["jazz", "club"], ["club", "film"])).toBe(true);
    expect(matchesGenres(["classical"], ["club", "film"])).toBe(false);
  });

  it("offers only genres with events today, in the given order", () => {
    expect(offeredGenres(["jazz", "pop", "classical", "film"], [["classical"], ["jazz", "club"]])).toEqual([
      "jazz",
      "classical",
    ]);
  });

  it("narrows a stored selection to what is offered", () => {
    expect(effectiveSelection(["pop", "jazz"], ["jazz", "classical"])).toEqual(["jazz"]);
  });

  it("remembers the selection per city, robust to bad storage", () => {
    const store = memoryStore();
    writeGenreSelection(store, "amsterdam", ["jazz", "pop"]);
    expect(readGenreSelection(store, "amsterdam")).toEqual(["jazz", "pop"]);
    expect(readGenreSelection(store, "barcelona")).toEqual([]);
    expect(readGenreSelection(memoryStore({ "today-genres:amsterdam": "{nope" }), "amsterdam")).toEqual([]);
    const throwing = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    expect(readGenreSelection(throwing, "amsterdam")).toEqual([]);
    expect(() => writeGenreSelection(throwing, "amsterdam", ["jazz"])).not.toThrow();
  });
});

describe("map venues", () => {
  const meta = (t: string, g = "jazz"): TodayEventMeta => ({
    t,
    u: `https://example.org/${t}`,
    p: "10€",
    g,
    l: [g],
    ed: null,
    et: null,
    m: false,
  });
  const events = { "1": meta("A"), "2": meta("B", "club"), "3": meta("C") };
  const venues: Record<string, TodayVenue> = {
    bimhuis: { n: "Bimhuis", lat: 52.37, lng: 4.91 },
    paradiso: { n: "Paradiso", lat: 52.36, lng: 4.88 },
    nowhere: { n: "Nowhere", lat: null, lng: null },
  };

  it("groups visible rows per venue, time-ordered, and counts venues off the map", () => {
    const r = mapVenues(
      [
        { id: "1", venue: "paradiso", time: "22:00" },
        { id: "3", venue: "paradiso", time: "01:00" },
        { id: "2", venue: "paradiso", time: "20:00" },
        { id: "1", venue: "bimhuis", time: "" },
        { id: "3", venue: "nowhere", time: "20:00" },
        { id: "9", venue: "paradiso", time: "20:00" }, // unknown event: skipped
      ],
      events,
      venues,
    );
    expect(r.missing).toBe(1);
    expect(r.venues.map((v) => v.slug)).toEqual(["bimhuis", "paradiso"]);
    // Post-midnight sorts last, an unknown time first.
    expect(r.venues[1].items.map((i) => i.time)).toEqual(["20:00", "22:00", "01:00"]);
    expect(r.venues[1].genre).toBe("jazz");
  });
});
