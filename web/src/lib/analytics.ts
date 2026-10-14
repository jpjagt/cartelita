// Pure helpers behind the site's Umami instrumentation (docs/analytics.md):
// day offsets, buckets, path parsing and the navigation event a page change
// amounts to. No DOM, no window — the browser side is lib/track.ts.
import { CITIES } from "@/lib/cities";
import type { AnalyticsData, NavEvent, PageRef } from "@/lib/types";

/** Local yyyy-mm-dd of the agenda's logical "today": the calendar date,
    rolled back a day before 05:00 (post-midnight shows belong to the evening
    before; lib/agenda.ts, syncAgenda in Layout.astro). */
export function logicalToday(now: Date): string {
  const back = now.getHours() < 5 ? 1 : 0;
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - back);
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

/** Whole days from `today` to `date` (both yyyy-mm-dd): 0 today, 1 tomorrow,
    negative for a past day (a stale page). NaN-safe: an unparsable date is 0. */
export function dayOffset(date: string, today: string): number {
  const utc = (s: string) => {
    const [y, m, d] = s.split("-").map(Number);
    return Date.UTC(y, m - 1, d);
  };
  const days = Math.round((utc(date) - utc(today)) / 86_400_000);
  return Number.isFinite(days) ? days : 0;
}

/** Day offsets bucketed for the "how far ahead do people look" report. */
export function depthBucket(offset: number): string {
  if (offset <= 0) return "0";
  if (offset === 1) return "1";
  if (offset === 2) return "2";
  if (offset <= 6) return "3-6";
  if (offset <= 13) return "7-13";
  if (offset <= 29) return "14-29";
  return "30+";
}

/** A count (favourite venues) bucketed so it reads as a segment. */
export function countBucket(n: number): string {
  if (n <= 0) return "0";
  if (n === 1) return "1";
  if (n <= 4) return "2-4";
  if (n <= 9) return "5-9";
  return "10+";
}

const SEARCH = /(^|\.)(google|bing|duckduckgo|yahoo|yandex|ecosia|baidu|qwant|startpage|kagi)\.|^search\.brave\.com$/;
const SOCIAL =
  /(^|\.)(facebook|fb|instagram|twitter|x|t|linkedin|lnkd|reddit|whatsapp|telegram|vk|threads|tiktok|youtube|pinterest|bsky|mastodon)\.(com|co|me|net|org|social|app)$/;

/** The kind of place a visit came from, for the `landing` event (the
    referrer host itself is in Umami's own Referrers report). */
export function referrerSource(referrer: string, ownHost: string): string {
  if (!referrer) return "direct";
  let host: string;
  try {
    host = new URL(referrer).hostname.replace(/^www\./, "");
  } catch {
    return "other";
  }
  if (host === ownHost.replace(/^www\./, "")) return "internal";
  if (SEARCH.test(host)) return "search";
  if (SOCIAL.test(host)) return "social";
  return "other";
}

/** City, locale and list of a site path. The bare /:city and /:city/:locale
    pages show the city's default locale/list, so they resolve to those. */
export function pageOfPath(pathname: string): PageRef {
  const [city = "", second = "", third = ""] = pathname.split("/").filter(Boolean);
  const cfg = CITIES[city];
  if (!cfg) return { city: "", locale: "", list: "" };
  const locale = second || cfg.defaultLocale;
  return { city, locale, list: third || cfg.defaultList };
}

/** The navigation event for going from `from` to `to`, by what changed most
    coarsely (a city switch may change all three), or null for a same-page
    navigation. `via` says how (navbar tab, locale cell, history …). */
export function navEvent(from: PageRef, to: PageRef, via: string): NavEvent | null {
  if (from.city !== to.city) {
    const data: AnalyticsData = { from: from.city || "none", to: to.city || "none", list: to.list, via };
    return { name: "city_switch", data };
  }
  if (from.locale !== to.locale) {
    return {
      name: "locale_switch",
      data: { from: from.locale, to: to.locale, city: to.city, list: to.list, via },
    };
  }
  if (from.list !== to.list) {
    return {
      name: "nav_tab",
      data: { from_list: from.list, to_list: to.list, city: to.city, locale: to.locale, via },
    };
  }
  return null;
}
