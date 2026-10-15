// Browser side of the Umami instrumentation (docs/analytics.md). Every call is
// guarded: with Umami blocked, not yet loaded or throwing, tracking is a
// silent no-op — it never gets in the way of what the click was for.
//
// Events go through umami.track rather than declarative data-umami-event
// attributes: Umami's own click handler turns a same-tab <a> carrying one
// into preventDefault + location.href (a full reload, past the ClientRouter),
// and attribute values are static strings, while most properties here (day
// offset, position, favourite state, share outcome) are only known on click.
import { countBucket, dayOffset, logicalToday } from "@/lib/analytics";
import { browserStore, readFavourites } from "@/lib/favourites";
import type { AnalyticsData } from "@/lib/types";

/** The page every event happened on: city, locale, list (body data-city,
    <html lang>, body data-genre — swapped with each client navigation, so
    read at event time), and the active view on pages that switch views. */
export function pageContext(): AnalyticsData {
  const body = document.body;
  const ctx: AnalyticsData = {
    city: body?.dataset.city ?? "",
    locale: document.documentElement.lang,
    list: body?.dataset.genre ?? "",
  };
  const view = document.querySelector<HTMLElement>("[data-view-root]")?.dataset.activeView;
  if (view) ctx.view = view;
  return ctx;
}

/** Send one event, with the page context under the event's own properties
    (`context: false` for events that carry their own city/locale/list). */
export function track(name: string, data: AnalyticsData = {}, context = true): void {
  try {
    window.umami?.track(name, context ? { ...pageContext(), ...data } : data);
  } catch {
    // Analytics never breaks the page.
  }
}

/** Run `fn` once Umami's (deferred) script is in, or never if it's blocked. */
export function whenUmami(fn: () => void): void {
  if (window.umami || document.readyState === "complete") {
    if (window.umami) fn();
    return;
  }
  window.addEventListener("load", () => window.umami && fn(), { once: true });
}

/** The favourite-venue count, bucketed (a segment: has the visitor set up My
    list?). */
export function favouritesBucket(): string {
  return countBucket(readFavourites(browserStore()).size);
}

/** Days from the agenda's logical today to the day section holding `el`
    (0 = today), or undefined outside a day. */
export function dayOffsetOf(el: Element): number | undefined {
  const date = el.closest<HTMLElement>("section[data-date]")?.dataset.date;
  return date ? dayOffset(date, logicalToday(new Date())) : undefined;
}

/** An event row's (film showtime's, Today map panel row's) properties: its category, venue, day
    offset and 1-based position among the day's visible rows (film cards for a
    showtime). No titles: venue slugs and genres only. */
export function eventProps(el: Element): AnalyticsData {
  const data: AnalyticsData = {};
  const row = el.closest<HTMLElement>("[data-event-row], [data-film-showtime], [data-map-event]");
  if (!row) return data;
  if (row.matches("[data-map-event]")) {
    // A Today map panel row: today, its position in the venue's list.
    if (row.dataset.genre) data.category = row.dataset.genre;
    if (row.dataset.venue) data.venue = row.dataset.venue;
    data.day_offset = 0;
    if (row.dataset.position) data.position = Number(row.dataset.position);
    return data;
  }
  const category = row.dataset.genre;
  if (category) data.category = category;
  if (row.dataset.venue) data.venue = row.dataset.venue;
  const offset = dayOffsetOf(row);
  if (offset !== undefined) data.day_offset = offset;
  const section = row.closest("section[data-date]");
  if (section) {
    const card = row.closest("[data-film-card]");
    const peers = card
      ? [...section.querySelectorAll("[data-film-card]")]
      : [...section.querySelectorAll<HTMLElement>("[data-event-row]")].filter((r) => !r.hidden);
    const i = peers.indexOf(card ?? row);
    if (i >= 0) data.position = i + 1;
  }
  return data;
}
