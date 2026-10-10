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
