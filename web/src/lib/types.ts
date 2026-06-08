export type Locale = "ca" | "es" | "en";
export const LOCALES: Locale[] = ["ca", "es", "en"];
export const DEFAULT_LOCALE: Locale = "ca";
export const DEFAULT_LIST = "jazz";

export interface CategoryList {
  slug: string;        // also the category slug, used for name translation
}

export interface AgendaEvent {
  id: number;
  title: string;       // resolved for the active locale (translation ?? canonical)
  startDate: string;   // ISO yyyy-mm-dd
  startTime: string | null; // 'HH:MM' or null
  venueName: string;
  price: string | null;
  sourceUrl: string;   // resolved for the active locale
  recurrenceHint: string | null;
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
export interface PackedFilm {
  film: FilmGroup;
  height: number;     // card height in cells = 1 (title) + showtimes.length
  col3: number;       // 0-based column index in the 3-column packing
  row3: number;       // 0-based row offset within the day in the 3-column packing
  col2: number;       // 0-based column index in the 2-column packing
  row2: number;       // 0-based row offset within the day in the 2-column packing
  row1: number;       // 0-based row offset in the single-column (mobile) stack,
                      // where each showtime occupies 2 rows
}

export interface FilmDayLayout {
  date: string;        // ISO yyyy-mm-dd
  films: PackedFilm[];
  rows3: number;       // total cell rows consumed by the 3-column packing
  rows2: number;       // total cell rows consumed by the 2-column packing
  rows1: number;       // total cell rows consumed by the single-column stack
}
