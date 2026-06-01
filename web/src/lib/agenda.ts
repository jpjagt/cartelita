import type { AgendaEvent, AgendaDay } from "@/lib/types";

/** Group a chronologically-sorted event list into per-day buckets, preserving order. */
export function groupEventsByDay(events: AgendaEvent[]): AgendaDay[] {
  const days: AgendaDay[] = [];
  for (const ev of events) {
    let day = days[days.length - 1];
    if (!day || day.date !== ev.startDate) {
      day = { date: ev.startDate, events: [] };
      days.push(day);
    }
    day.events.push(ev);
  }
  return days;
}
