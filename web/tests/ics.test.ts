import { describe, it, expect } from "vitest";
import { buildIcs, escapeIcsText, foldIcsLine, zonedToUtc } from "@/lib/ics";
import type { ShareEvent } from "@/lib/types";

const iso = (ms: number) => new Date(ms).toISOString();
const AMS = "Europe/Amsterdam";

describe("zonedToUtc", () => {
  it("converts summer (CEST, +2) and winter (CET, +1) times", () => {
    expect(iso(zonedToUtc("2026-10-10", "20:30", AMS))).toBe("2026-10-10T18:30:00.000Z");
    expect(iso(zonedToUtc("2026-12-01", "20:30", AMS))).toBe("2026-12-01T19:30:00.000Z");
    expect(iso(zonedToUtc("2026-07-01", "21:00", "Europe/Madrid"))).toBe("2026-07-01T19:00:00.000Z");
    expect(iso(zonedToUtc("2026-07-01", "21:00", "Asia/Yerevan"))).toBe("2026-07-01T17:00:00.000Z");
  });

  it("handles the evening of a fall-back day (25 Oct 2026)", () => {
    // Clocks go back at 03:00 CEST that morning; the evening is CET.
    expect(iso(zonedToUtc("2026-10-25", "20:30", AMS))).toBe("2026-10-25T19:30:00.000Z");
    expect(iso(zonedToUtc("2026-10-25", "01:30", AMS))).toBe("2026-10-24T23:30:00.000Z");
    // 02:30 happens twice: the first (CEST) occurrence wins.
    expect(iso(zonedToUtc("2026-10-25", "02:30", AMS))).toBe("2026-10-25T00:30:00.000Z");
    expect(iso(zonedToUtc("2026-10-25", "03:30", AMS))).toBe("2026-10-25T02:30:00.000Z");
  });

  it("handles a spring-forward day (29 Mar 2026)", () => {
    expect(iso(zonedToUtc("2026-03-29", "01:30", AMS))).toBe("2026-03-29T00:30:00.000Z");
    expect(iso(zonedToUtc("2026-03-29", "03:30", AMS))).toBe("2026-03-29T01:30:00.000Z");
    expect(iso(zonedToUtc("2026-03-29", "20:00", AMS))).toBe("2026-03-29T18:00:00.000Z");
    // 02:30 doesn't exist: pushed forward by the gap, to 03:30 CEST.
    expect(iso(zonedToUtc("2026-03-29", "02:30", AMS))).toBe("2026-03-29T01:30:00.000Z");
  });
});

describe("escapeIcsText / foldIcsLine", () => {
  it("escapes backslash, semicolon, comma and newlines", () => {
    expect(escapeIcsText("a\\b;c,d\ne\r\nf")).toBe("a\\\\b\\;c\\,d\\ne\\nf");
  });

  it("leaves short lines alone and folds long ones at 75 octets", () => {
    expect(foldIcsLine("SUMMARY:short")).toBe("SUMMARY:short");
    const folded = foldIcsLine("SUMMARY:" + "x".repeat(200));
    const lines = folded.split("\r\n");
    expect(lines.length).toBeGreaterThan(2);
    expect(lines[0]).toHaveLength(75);
    for (const l of lines.slice(1)) {
      expect(l.startsWith(" ")).toBe(true);
      expect(l.length).toBeLessThanOrEqual(75);
    }
    expect(lines.map((l, i) => (i ? l.slice(1) : l)).join("")).toBe("SUMMARY:" + "x".repeat(200));
  });

  it("never splits a multi-byte character", () => {
    const enc = new TextEncoder();
    const line = "SUMMARY:" + "Սպառված ".repeat(20);
    const lines = foldIcsLine(line).split("\r\n");
    for (const l of lines) expect(enc.encode(l).length).toBeLessThanOrEqual(75);
    expect(lines.map((l, i) => (i ? l.slice(1) : l)).join("")).toBe(line);
  });
});

describe("buildIcs", () => {
  const ev: ShareEvent = {
    id: "1234",
    title: "Artved Quartet; live, at last",
    date: "2026-10-10",
    time: "20:30",
    venue: "Bimhuis",
    price: "13€",
    url: "https://www.bimhuis.nl/agenda/artved-quartet?x=1,2",
  };
  const now = new Date("2026-10-01T12:00:00Z");
  const unfold = (s: string) => s.replace(/\r\n /g, "");

  it("builds a timed VEVENT in UTC with a 2h default duration", () => {
    const ics = buildIcs(ev, AMS, now);
    expect(ics.endsWith("\r\n")).toBe(true);
    expect(ics.split("\r\n").every((l) => !l.includes("\n"))).toBe(true);
    const body = unfold(ics);
    expect(body).toContain("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n");
    expect(body).toContain("UID:1234-20261010T2030@cartelita.co\r\n");
    expect(body).toContain("DTSTAMP:20261001T120000Z\r\n");
    expect(body).toContain("DTSTART:20261010T183000Z\r\n");
    expect(body).toContain("DTEND:20261010T203000Z\r\n");
    expect(body).toContain("SUMMARY:Artved Quartet\\; live\\, at last\r\n");
    expect(body).toContain("LOCATION:Bimhuis\r\n");
    expect(body).toContain("DESCRIPTION:13€\\nhttps://www.bimhuis.nl/agenda/artved-quartet?x=1\\,2\r\n");
    expect(body).toContain("URL:https://www.bimhuis.nl/agenda/artved-quartet?x=1,2\r\n");
    expect(body).toContain("END:VEVENT\r\nEND:VCALENDAR\r\n");
  });

  it("makes timeless events all-day", () => {
    const body = unfold(buildIcs({ ...ev, time: null }, AMS, now));
    expect(body).toContain("DTSTART;VALUE=DATE:20261010\r\n");
    expect(body).toContain("DTEND;VALUE=DATE:20261011\r\n");
    expect(body).toContain("UID:1234-20261010@cartelita.co\r\n");
  });

  it("all-day end rolls over month and year ends", () => {
    expect(buildIcs({ ...ev, time: null, date: "2026-12-31" }, AMS, now)).toContain(
      "DTEND;VALUE=DATE:20270101",
    );
  });

  it("uses the event's real date for a post-midnight show", () => {
    // Shown under Fri 9 Oct's evening in the agenda; really Sat 10 Oct 01:00 CEST.
    const body = unfold(buildIcs({ ...ev, date: "2026-10-10", time: "01:00" }, AMS, now));
    expect(body).toContain("DTSTART:20261009T230000Z\r\n");
    expect(body).toContain("DTEND:20261010T010000Z\r\n");
  });

  it("omits the price line from the description when there's no price", () => {
    const body = unfold(buildIcs({ ...ev, price: "" }, AMS, now));
    expect(body).toContain("DESCRIPTION:https://www.bimhuis.nl/agenda/artved-quartet?x=1\\,2\r\n");
  });

  it("folds long titles", () => {
    const ics = buildIcs({ ...ev, title: "A very long concert title ".repeat(6) }, AMS, now);
    for (const l of ics.split("\r\n")) expect(new TextEncoder().encode(l).length).toBeLessThanOrEqual(75);
  });
});
