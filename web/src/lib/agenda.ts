import type { AgendaEvent, AgendaDay } from "@/lib/types";

/** Events 00:00–04:59 belong to the previous calendar day (late night of that evening). */
function logicalDate(startDate: string, startTime: string | null): string {
  if (startTime && startTime < "05:00") {
    const [y, m, d] = startDate.split("-").map(Number);
    return new Date(Date.UTC(y, m - 1, d - 1)).toISOString().slice(0, 10);
  }
  return startDate;
}

/** Sort key: null first, then times ≥ 05:00 ascending, then times < 05:00 (post-midnight) last. */
function timeSortKey(t: string | null): string {
  if (t === null) return "0";
  if (t >= "05:00") return "1" + t;
  return "2" + t;
}

/** Group events into per-day buckets using 05:00 as the day boundary. */
export function groupEventsByDay(events: AgendaEvent[]): AgendaDay[] {
  const buckets = new Map<string, AgendaEvent[]>();
  for (const ev of events) {
    const date = logicalDate(ev.startDate, ev.startTime);
    if (!buckets.has(date)) buckets.set(date, []);
    buckets.get(date)!.push(ev);
  }
  const days: AgendaDay[] = [];
  for (const date of [...buckets.keys()].sort()) {
    const evs = buckets.get(date)!;
    evs.sort((a, b) => timeSortKey(a.startTime).localeCompare(timeSortKey(b.startTime)));
    days.push({ date, events: evs });
  }
  return days;
}
