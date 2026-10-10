import type { ShareEvent, ShareStrings } from "@/lib/types";

/** "Sat 10 Oct" for an ISO yyyy-mm-dd, in the page's locale. The date is a
    plain calendar date, so it is formatted in UTC to keep the visitor's own
    time zone from shifting it a day. */
export function formatShareDate(date: string, localeTag: string): string {
  const [y, m, d] = date.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(localeTag, {
    timeZone: "UTC",
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

/** The share-sheet / clipboard text for one event, e.g.
    "Artved Quartet — Sat 10 Oct, 20:30 at Bimhuis (13€)". The time part is
    dropped for timeless events and "(price)" when there is no price. The URL is
    not part of it (navigator.share takes it separately; the clipboard fallback
    appends it). */
export function shareText(ev: ShareEvent, s: ShareStrings): string {
  const when = [formatShareDate(ev.date, s.localeTag), ev.time]
    .filter(Boolean)
    .join(", ");
  // Function replacers, so a "$&" in a title isn't read as a pattern.
  const text = s.template
    .replace("{title}", () => ev.title)
    .replace("{when}", () => when)
    .replace("{venue}", () => ev.venue);
  return ev.price ? `${text} (${ev.price})` : text;
}
