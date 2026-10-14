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

/** The only genres that may ever get a top-level navbar tab. Every other
    category (kids, folk, flamenco, and any future one not listed here) always
    sits behind "More", however busy it is. The allowed ones still earn their
    tab by volume (earnsTab) and still fall into More when thin or when they
    don't fit the bar. */
export const TOP_LEVEL_GENRES: readonly string[] = [
  "jazz",
  "theater",
  "dance",
  "classical",
  "club",
  "pop",
  "alternative",
  "rock",
];

/** Whether a genre may get a top-level tab at all (TOP_LEVEL_GENRES). */
export function isTopLevel(list: CategoryList): boolean {
  return TOP_LEVEL_GENRES.includes(list.slug);
}

/** A city's genre lists in navbar order: the top-level genres by volume,
    then the always-More ones by volume. Since tabs are a prefix of this order
    and More holds the rest, More lists the allowed-but-thin (or overflowing)
    genres first, then the always-More ones, each busiest first. */
export function navOrder(lists: CategoryList[]): CategoryList[] {
  const ordered = orderByVolume(lists);
  return [...ordered.filter(isTopLevel), ...ordered.filter((l) => !isTopLevel(l))];
}

/** Order a city's lists by upcoming volume, busiest first; ties
    alphabetically by slug, so the order is the same in every locale. */
export function orderByVolume(lists: CategoryList[]): CategoryList[] {
  return [...lists].sort((a, b) => b.upcoming - a.upcoming || a.slug.localeCompare(b.slug));
}

/** Whether a list is busy enough for its own tab. */
export function earnsTab(list: CategoryList): boolean {
  return (list.upcoming / NAV_WINDOW_DAYS) * 7 >= MORE_THRESHOLD_PER_WEEK;
}

/** How many leading genres of `genres` (navOrder) may ever get a tab: the
    TOP_LEVEL_GENRES run. */
export function topLevelCount(genres: CategoryList[]): number {
  let k = 0;
  while (k < genres.length && isTopLevel(genres[k])) k++;
  return k;
}

/** How many leading genres of `genres` (navOrder) qualify for a tab: the run
    of top-level genres that clears the weekly threshold. When none does, the
    busiest top-level one still gets a tab if it has anything at all, so the
    bar is never just "More". The navbar may show fewer when they don't fit
    (lib/nav-layout.ts). */
export function tabbableCount(genres: CategoryList[]): number {
  let k = 0;
  while (k < genres.length && isTopLevel(genres[k]) && earnsTab(genres[k])) k++;
  if (k === 0 && genres.length > 0 && isTopLevel(genres[0]) && genres[0].upcoming > 0) k = 1;
  return k;
}
