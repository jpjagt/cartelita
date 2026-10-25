import { logicalDate, timeSortKey } from "@/lib/agenda";
import type {
  AgendaClock,
  MapVenue,
  MapVenues,
  RemainingInput,
  TodayEventMeta,
  TodayVenue,
  VisibleRow,
  WallClock,
} from "@/types/today";

// The Today page's rules, pure (no DOM) so they're unit-tested apart from the
// page script (pages/[city]/[locale]/today.astro).
//
// "Today" is the city's, not the visitor's: the static site is rebuilt only
// nightly, so the page ships several days and the client picks today in the
// city's time zone, in the agenda's logical-day frame (lib/agenda.ts: before
// 05:00 still counts as the evening before, so post-midnight shows belong to
// it).

/** How many logical days a Today page ships, from the build's today: today
    plus tomorrow, and one more so a page survives one failed nightly build. */
export const TODAY_SHIP_DAYS = 3;

/** An event without a known end drops off this long after it started. */
export const STARTED_GRACE_MIN = 120;

/** How often an open Today page re-applies the time rule. */
export const TODAY_TICK_MS = 60_000;

/** localStorage key prefix for the per-city genre selection. */
export const TODAY_GENRES_KEY = "today-genres";

const pad = (n: number) => String(n).padStart(2, "0");

/** The wall clock (date + HH:MM, 24h) at `now` in time zone `tz`, or in the
    browser's own zone when `tz` is absent or unknown. */
export function wallClock(now: Date, tz?: string): WallClock {
  if (tz) {
    try {
      const parts = new Intl.DateTimeFormat("en-CA", {
        timeZone: tz,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
      }).formatToParts(now);
      const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
      return { date: `${get("year")}-${get("month")}-${get("day")}`, time: `${get("hour")}:${get("minute")}` };
    } catch {
      // Unknown zone: fall through to the browser's.
    }
  }
  return {
    date: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`,
    time: `${pad(now.getHours())}:${pad(now.getMinutes())}`,
  };
}

/** The city's logical today (yyyy-mm-dd) at `now`. */
export function cityToday(now: Date, tz?: string): string {
  const c = wallClock(now, tz);
  return logicalDate(c.date, c.time);
}

/** The day a nightly build's Today preview (description + OG image) is for:
    the city's CALENDAR date at `now`, not its logical one — the ~05:00
    Madrid build runs before London's (04:00) and Asunción's (00:00) 05:00
    boundary, when the logical day is still yesterday. */
export function ogDay(now: Date, tz?: string): string {
  return wallClock(now, tz).date;
}

/** `date` (yyyy-mm-dd) shifted by `days`. */
export function addDays(date: string, days: number): string {
  const [y, m, d] = date.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

/** Minutes on a zone-less wall-clock axis (comparable within one city). */
export function wallMinutes(date: string, time: string): number {
  const [y, m, d] = date.split("-").map(Number);
  const [h, mi] = time.split(":").map(Number);
  return Date.UTC(y, m - 1, d, h, mi) / 60_000;
}

/** syncAgenda's clock (Layout.astro): logical date, now's sort key and the
    sort key of two hours ago, on the city's wall clock (`tz`) or the
    browser's. */
export function agendaClock(now: Date, tz?: string): AgendaClock {
  const c = wallClock(now, tz);
  const before = wallClock(new Date(now.getTime() - STARTED_GRACE_MIN * 60_000), tz);
  return {
    logicalDate: logicalDate(c.date, c.time),
    nowKey: timeSortKey(c.time),
    cutoffKey: timeSortKey(before.time),
  };
}

/** When a row stops showing, in wallMinutes, or null when it never does
    today (no start time: all-day or unknown).
    - A known end (end time; end date, else the start's date — rolled to the
      next day when the end time isn't after the start, an overnight club
      night) ends it then. A multi-showtime event's single end is ignored:
      each screening is its own row.
    - An end date after the start but no end time (a run over several days)
      lasts the whole (logical) day.
    - Otherwise it drops STARTED_GRACE_MIN after it started. */
export function rowEnd(row: RemainingInput): number | null {
  if (!row.time) return null;
  const start = wallMinutes(row.date, row.time);
  if (!row.multi && row.endTime) {
    let end = wallMinutes(row.endDate ?? row.date, row.endTime);
    if (end <= start && (!row.endDate || row.endDate <= row.date)) end += 24 * 60;
    if (end > start) return end;
  }
  if (!row.multi && row.endDate && row.endDate > row.date) {
    return wallMinutes(addDays(row.endDate, 1), "05:00");
  }
  return start + STARTED_GRACE_MIN;
}

/** Whether a row still shows at wall clock `now`: before its end (rowEnd). */
export function isRemaining(row: RemainingInput, now: WallClock): boolean {
  const end = rowEnd(row);
  return end === null || wallMinutes(now.date, now.time) < end;
}

/** Whether an event in `lists` passes the genre selection: no genre selected
    shows everything; otherwise any selected genre will do. */
export function matchesGenres(lists: readonly string[], selected: readonly string[]): boolean {
  return selected.length === 0 || lists.some((l) => selected.includes(l));
}

/** The genres to offer, in `order`: those with at least one event today. */
export function offeredGenres(order: readonly string[], todayLists: Iterable<readonly string[]>): string[] {
  const present = new Set<string>();
  for (const lists of todayLists) lists.forEach((l) => present.add(l));
  return order.filter((g) => present.has(g));
}

/** The stored selection narrowed to what's offered today (a genre with
    nothing today can't filter anything; it stays stored for another day). */
export function effectiveSelection(stored: readonly string[], offered: readonly string[]): string[] {
  return stored.filter((g) => offered.includes(g));
}

type KeyValueStore = Pick<Storage, "getItem" | "setItem">;

const genresKey = (city: string) => `${TODAY_GENRES_KEY}:${city}`;

/** The city's remembered genre selection; missing, corrupt or blocked
    storage reads as none (= everything). */
export function readGenreSelection(store: KeyValueStore, city: string): string[] {
  try {
    const parsed: unknown = JSON.parse(store.getItem(genresKey(city)) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((s): s is string => typeof s === "string") : [];
  } catch {
    return [];
  }
}

/** Remember the city's genre selection (best effort). */
export function writeGenreSelection(store: KeyValueStore, city: string, genres: readonly string[]): void {
  try {
    store.setItem(genresKey(city), JSON.stringify([...genres]));
  } catch {
    // Not persisted; the page still filters for this visit.
  }
}

/** Group the visible rows by venue for the map: each venue's events in row
    order (one entry per showtime), venues without coordinates counted
    instead. Venue order: by name. */
export function mapVenues(
  rows: readonly VisibleRow[],
  events: Record<string, TodayEventMeta>,
  venues: Record<string, TodayVenue>,
): MapVenues {
  const byVenue = new Map<string, MapVenue>();
  const missing = new Set<string>();
  const seen = new Set<string>();
  for (const row of rows) {
    const meta = events[row.id];
    const venue = venues[row.venue];
    if (!meta || !venue) continue;
    if (venue.lat === null || venue.lng === null) {
      missing.add(row.venue);
      continue;
    }
    // A showtime can appear twice (an event row and a film card share none,
    // but guard anyway): one entry per (event, time).
    const key = `${row.id}@${row.time}`;
    if (seen.has(key)) continue;
    seen.add(key);
    let v = byVenue.get(row.venue);
    if (!v) {
      v = { slug: row.venue, name: venue.n, lat: venue.lat, lng: venue.lng, genre: meta.g, items: [] };
      byVenue.set(row.venue, v);
    }
    v.items.push({ id: row.id, time: row.time, title: meta.t, url: meta.u, price: meta.p, genre: meta.g });
  }
  for (const v of byVenue.values()) {
    v.items.sort((a, b) => timeSortKey(a.time || null).localeCompare(timeSortKey(b.time || null)));
  }
  return {
    venues: [...byVenue.values()].sort((a, b) => a.name.localeCompare(b.name)),
    missing: missing.size,
  };
}
