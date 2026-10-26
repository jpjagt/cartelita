import type { ShareEvent } from "@/lib/types";

// "Add to calendar": an RFC 5545 VCALENDAR with one VEVENT, built in the
// browser and handed to the OS as a text/calendar blob (see ShareMenu.astro).
// Event times are wall-clock times in the city's zone, so timed events are
// converted to UTC here (no VTIMEZONE block needed); timeless events become
// all-day events.

// Kept on the original domain: changing it would change every event UID, so
// re-adding an event would duplicate it in calendars instead of updating it.
const UID_DOMAIN = "cartelita.july.dev";
/** Assumed length when the source gives no end time. */
const DEFAULT_DURATION_MS = 2 * 60 * 60 * 1000;

const formatters = new Map<string, Intl.DateTimeFormat>();
function formatterFor(timeZone: string): Intl.DateTimeFormat {
  let f = formatters.get(timeZone);
  if (!f) {
    f = new Intl.DateTimeFormat("en-US", {
      timeZone,
      hourCycle: "h23",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    formatters.set(timeZone, f);
  }
  return f;
}

/** The zone's UTC offset (ms, east positive) at a given instant. */
function offsetAt(utcMs: number, timeZone: string): number {
  const p: Record<string, number> = {};
  for (const part of formatterFor(timeZone).formatToParts(new Date(utcMs))) {
    if (part.type !== "literal") p[part.type] = Number(part.value);
  }
  const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
  return asUtc - Math.floor(utcMs / 1000) * 1000;
}

/** Convert a wall-clock date + 'HH:MM' in `timeZone` to a UTC instant (ms).
    DST is handled like Temporal's "compatible" disambiguation: a time repeated
    by a fall-back transition resolves to its first (earlier) occurrence; a time
    skipped by a spring-forward gap is pushed forward by the gap (02:30 → 03:30). */
export function zonedToUtc(date: string, time: string, timeZone: string): number {
  const [y, mo, d] = date.split("-").map(Number);
  const [h, mi] = time.split(":").map(Number);
  const local = Date.UTC(y, mo - 1, d, h, mi);
  const DAY = 24 * 60 * 60 * 1000;
  // A transition never happens twice within a day, so the offsets a day
  // either side bracket every possible answer.
  const before = offsetAt(local - DAY, timeZone);
  const after = offsetAt(local + DAY, timeZone);
  const valid = [local - before, local - after].filter(
    (t) => t + offsetAt(t, timeZone) === local,
  );
  if (valid.length) return Math.min(...valid);
  return local - before; // in the gap
}

/** yyyymmddThhmmssZ */
function utcStamp(ms: number): string {
  return new Date(ms).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

/** yyyymmdd of `date` plus `days`. */
function dateValue(date: string, days = 0): string {
  const [y, m, d] = date.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10).replace(/-/g, "");
}

/** Escape a TEXT value (RFC 5545 §3.3.11). */
export function escapeIcsText(s: string): string {
  return s
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,")
    .replace(/\r\n|\r|\n/g, "\\n");
}

/** Fold a content line to ≤75 octets per physical line (RFC 5545 §3.1):
    continuation lines start with one space. Splits only between characters,
    never inside a multi-byte UTF-8 sequence. */
export function foldIcsLine(line: string): string {
  const enc = new TextEncoder();
  const out: string[] = [];
  let cur = "";
  let octets = 0;
  for (const ch of line) {
    const n = enc.encode(ch).length;
    // The first line holds 75 octets; continuations 74 (+ the leading space).
    const limit = out.length === 0 ? 75 : 74;
    if (octets + n > limit) {
      out.push(cur);
      cur = "";
      octets = 0;
    }
    cur += ch;
    octets += n;
  }
  out.push(cur);
  return out.join("\r\n ");
}

/** A complete .ics for one event. `now` is the DTSTAMP (injectable for tests). */
export function buildIcs(ev: ShareEvent, timeZone: string, now: Date = new Date()): string {
  let start: string;
  let end: string;
  if (ev.time) {
    const startMs = zonedToUtc(ev.date, ev.time, timeZone);
    start = `DTSTART:${utcStamp(startMs)}`;
    end = `DTEND:${utcStamp(startMs + DEFAULT_DURATION_MS)}`;
  } else {
    start = `DTSTART;VALUE=DATE:${dateValue(ev.date)}`;
    end = `DTEND;VALUE=DATE:${dateValue(ev.date, 1)}`;
  }
  const uidWhen = dateValue(ev.date) + (ev.time ? `T${ev.time.replace(":", "")}` : "");
  const description = [ev.price, ev.url].filter(Boolean).join("\n");
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Cartelita//cartelita.july.dev//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${ev.id}-${uidWhen}@${UID_DOMAIN}`,
    `DTSTAMP:${utcStamp(now.getTime())}`,
    start,
    end,
    `SUMMARY:${escapeIcsText(ev.title)}`,
    `LOCATION:${escapeIcsText(ev.venue)}`,
    `DESCRIPTION:${escapeIcsText(description)}`,
    // URL is a URI value, not TEXT: no backslash escaping.
    ...(ev.url ? [`URL:${ev.url}`] : []),
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return lines.map(foldIcsLine).join("\r\n") + "\r\n";
}
