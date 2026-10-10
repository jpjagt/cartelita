import { describe, it, expect } from "vitest";
import { shareText, formatShareDate } from "@/lib/share";
import { t, localeTag } from "@/i18n";
import type { Locale, ShareEvent } from "@/lib/types";

const ev: ShareEvent = {
  id: "42",
  title: "Artved Quartet",
  date: "2026-10-10",
  time: "20:30",
  venue: "Bimhuis",
  price: "13€",
  url: "https://www.bimhuis.nl/agenda/artved",
};
const strings = (locale: Locale) => ({
  localeTag: localeTag(locale),
  template: t(locale).shareTemplate,
});

describe("shareText", () => {
  it("formats title, date, time, venue and price (en)", () => {
    expect(shareText(ev, strings("en"))).toBe(
      "Artved Quartet — Sat 10 Oct, 20:30 at Bimhuis (13€)",
    );
  });

  it("drops the time part for timeless events", () => {
    expect(shareText({ ...ev, time: null }, strings("en"))).toBe(
      "Artved Quartet — Sat 10 Oct at Bimhuis (13€)",
    );
  });

  it("drops the price when there is none", () => {
    expect(shareText({ ...ev, price: "" }, strings("en"))).toBe(
      "Artved Quartet — Sat 10 Oct, 20:30 at Bimhuis",
    );
    expect(shareText({ ...ev, price: "", time: null }, strings("en"))).toBe(
      "Artved Quartet — Sat 10 Oct at Bimhuis",
    );
  });

  it("localizes the date and connective (nl, es)", () => {
    const nl = shareText({ ...ev, price: t("nl").prices["sold-out"] }, strings("nl"));
    expect(nl).toBe(`Artved Quartet — ${formatShareDate(ev.date, "nl-NL")}, 20:30 in Bimhuis (Uitverkocht)`);
    expect(nl).toMatch(/za.*10.*okt/);
    expect(shareText(ev, strings("es"))).toContain(", 20:30 en Bimhuis (13€)");
  });

  it("uses the real calendar date for a post-midnight event", () => {
    // Listed under Fri 9 Oct's evening in the agenda, but it is Sat 10 Oct.
    expect(shareText({ ...ev, date: "2026-10-10", time: "01:00" }, strings("en"))).toBe(
      "Artved Quartet — Sat 10 Oct, 01:00 at Bimhuis (13€)",
    );
  });

  it("does not treat $-patterns in titles as replacement patterns", () => {
    expect(shareText({ ...ev, title: "Cash $& Carry" }, strings("en"))).toMatch(/^Cash \$& Carry — /);
  });

  it("every locale has share strings and a complete template", () => {
    for (const locale of ["ca", "es", "en", "hy", "ru", "nl"] as const) {
      const s = t(locale);
      expect(s.share && s.addToCalendar && s.copied).toBeTruthy();
      for (const slot of ["{title}", "{when}", "{venue}"]) {
        expect(s.shareTemplate, `${locale} ${slot}`).toContain(slot);
      }
    }
  });
});
