import type { VenueGroup, VenueDirectoryLayout } from "@/lib/types";
import { packCards } from "@/lib/masonry";

/** Lay out the My list venue directory: one card per category list (title row
    + one row per venue), packed like the film cards. Empty lists are dropped. */
export function layoutVenueDirectory(groups: VenueGroup[]): VenueDirectoryLayout {
  const nonEmpty = groups.filter((g) => g.venues.length > 0);
  const layout = packCards(nonEmpty.map((g) => 1 + g.venues.length));
  return {
    groups: nonEmpty.map((group, i) => ({ group, ...layout.placements[i] })),
    rows3: layout.rows3,
    rows2: layout.rows2,
    rows1: layout.rows1,
  };
}

/** localStorage key holding the list slugs of collapsed directory cards. */
export const COLLAPSED_KEY = "venue-directory-collapsed";

/** Parse the stored collapsed-card slugs; anything malformed reads as none. */
export function parseCollapsed(raw: string | null): Set<string> {
  if (!raw) return new Set();
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? new Set(parsed.filter((s): s is string => typeof s === "string"))
      : new Set();
  } catch {
    return new Set();
  }
}

/** Card heights for the directory: a collapsed card is just its title row,
    an expanded one the title plus one row per venue. */
export function directoryHeights(
  venueCounts: number[],
  collapsed: boolean[],
): number[] {
  return venueCounts.map((n, i) => (collapsed[i] ? 1 : 1 + n));
}
