import type { CategoryList } from "@/lib/types";

// Which genre tabs a city's navbar shows, and in what order — pure, so it's
// testable apart from the query (lib/queries.ts getCategoryLists) that
// counts the events.

/** The look-ahead window the tab order and the More split count events in. */
export const NAV_WINDOW_DAYS = 28;

/** A genre averaging fewer events a week than this (over NAV_WINDOW_DAYS)
    goes behind the navbar's "More" dropdown rather than getting a tab. */
export const MORE_THRESHOLD_PER_WEEK = 5;

/** The film list: set apart in the navbar (with My list), never a genre tab. */
export const FILM_LIST = "film";

/** Order a city's lists by upcoming volume, busiest first; ties
    alphabetically by slug, so the order is the same in every locale. */
export function orderByVolume(lists: CategoryList[]): CategoryList[] {
  return [...lists].sort((a, b) => b.upcoming - a.upcoming || a.slug.localeCompare(b.slug));
}

/** Whether a list is busy enough for its own tab. */
export function earnsTab(list: CategoryList): boolean {
  return (list.upcoming / NAV_WINDOW_DAYS) * 7 >= MORE_THRESHOLD_PER_WEEK;
}

/** How many leading genres of `genres` (volume order) qualify for a tab:
    the run that clears the weekly threshold. When none does, the busiest one
    still gets a tab if it has anything at all, so the bar is never just
    "More". The navbar may show fewer when they don't fit (lib/nav-layout.ts). */
export function tabbableCount(genres: CategoryList[]): number {
  let k = 0;
  while (k < genres.length && earnsTab(genres[k])) k++;
  if (k === 0 && (genres[0]?.upcoming ?? 0) > 0) k = 1;
  return k;
}
