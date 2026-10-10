export type Locale = "ca" | "es" | "en" | "hy" | "ru" | "nl";

/** A city Cartelita runs in; which locales it serves and its landing list.
    The config values live in cities.ts. */
export interface CityConfig {
  slug: string;
  name: string;
  locales: Locale[];
  defaultLocale: Locale;
  defaultList: string;
  /** IANA time zone the city's wall-clock event times are in (calendar export). */
  timezone: string;
}

/** One option in a GridRadioButtons control. */
export interface GridRadioOption {
  value: string;
  label: string;
}

export interface CategoryList {
  slug: string;        // also the category slug, used for name translation
  primary: boolean;    // broad-appeal genre, shown full-weight in the navbar;
                       // niche genres (false) render muted so the eye skips them
}

export interface AgendaEvent {
  id: number;
  title: string;       // resolved for the active locale (translation ?? canonical)
  startDate: string;   // ISO yyyy-mm-dd
  startTime: string | null; // 'HH:MM' or null
  venueSlug: string;   // stable venue key; favourites are stored by it
  venueName: string;
  price: string | null;
  sourceUrl: string;   // resolved for the active locale
  recurrenceHint: string | null;
  language: string | null; // display-only performance/source language ("VOSE", "hy")
  /** Per-event genre for hover tinting, on pages mixing categories (My list).
      Category pages leave it unset and tint by the page's own list. */
  genre?: string;
}

/** A city-wide agenda event for the My list page, split into the Events and
    Films views by isFilm. */
export interface CityAgendaEvent extends AgendaEvent {
  isFilm: boolean;
}

export interface VenueRef {
  slug: string;
  name: string;
}

/** One category list's venues, for the My list venue directory. */
export interface VenueGroup {
  listSlug: string;
  venues: VenueRef[];
}

/** Where one card lands in each masonry packing (see lib/masonry.ts). */
export interface CardPlacement {
  col3: number;       // 0-based column index in the 3-column packing
  row3: number;       // 0-based row offset in the 3-column packing
  col2: number;       // 0-based column index in the 2-column packing
  row2: number;       // 0-based row offset in the 2-column packing
  row1: number;       // 0-based row offset in the single-column stack
}

/** Card placements plus the total cell rows each packing consumes. */
export interface MasonryLayout {
  placements: CardPlacement[];
  rows3: number;
  rows2: number;
  rows1: number;
}

/** A venue-directory card placed on the grid (same packing as film cards). */
export interface PackedVenueGroup extends CardPlacement {
  group: VenueGroup;
}

export interface VenueDirectoryLayout {
  groups: PackedVenueGroup[];
  rows3: number;
  rows2: number;
  rows1: number;
}

export interface AgendaDay {
  date: string;        // ISO yyyy-mm-dd
  events: AgendaEvent[];
}

/** One film within a day: its title shown once, with all its showtimes. */
export interface FilmGroup {
  title: string;            // resolved per-locale; the group key
  showtimes: AgendaEvent[]; // sorted by timeSortKey
  earliestKey: string;      // timeSortKey of the first showtime (film ordering)
  latestTime: string;       // startTime of the last showtime ("" if none); drives card collapse
}

/** A film card placed onto the shared cell grid at a given column + row offset.
    Both the 3-column and 2-column masonry packings are precomputed at build
    time; CSS media queries pick which (col/row) pair applies. */
export interface PackedFilm extends CardPlacement {
  film: FilmGroup;
  height: number;     // card height in cells = 1 (title) + showtimes.length
}

export interface FilmDayLayout {
  date: string;        // ISO yyyy-mm-dd
  films: PackedFilm[];
  rows3: number;       // total cell rows consumed by the 3-column packing
  rows2: number;       // total cell rows consumed by the 2-column packing
  rows1: number;       // total cell rows consumed by the single-column stack
}

/** The fields of one event row the share menu needs (read off the row's DOM /
    data-* attributes on the client; see lib/share.ts and lib/ics.ts). */
export interface ShareEvent {
  id: string;            // event id, for the calendar UID
  title: string;
  date: string;          // REAL calendar date, ISO yyyy-mm-dd (not the agenda's logical day)
  time: string | null;   // 'HH:MM' or null (timeless)
  venue: string;
  price: string;         // localized display price ("13€", "Sold out"), "" when none
  url: string;
}

/** Page-level localized bits for the share text (one set per page). */
export interface ShareStrings {
  /** BCP-47 tag for date formatting (localeTag). */
  localeTag: string;
  /** "{title} — {when} at {venue}"; " ({price})" is appended when there is one. */
  template: string;
}
