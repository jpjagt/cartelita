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
  /** Short excerpt of the description (translation ?? canonical), resolved
      per locale and cut at build (lib/description.ts); null when none. */
  description: string | null;
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

/** Icons drawn by CellIcon.astro (one <symbol> each in CellIconSprite.astro). */
export type CellIconName =
  | "share"
  | "heart"
  | "heart-filled"
  | "calendar"
  | "eye"
  | "chevron";

/** Where one agenda row lands (lib/event-panel.ts): its 0-based index (--ev)
    and the extra grid rows open event panels push in above it (--po). */
export interface RowNumbering {
  ev: number;
  po: number;
}

/** The navbar's band geometry, in grid column lines (lib/nav-layout.ts). */
export interface NavGeometry {
  colStart: number;     // first column of the content band
  bandEnd: number;      // exclusive end line of the band
  localeCount: number;  // locale switcher cells at the right of row 1
  narrow: boolean;      // the narrow (<760px) stacked layout
}

/** One navbar link's grid placement. */
export interface NavPlacement {
  col: number;
  span: number;
  row: number;
}

/** One locale switcher cell's placement (lib/nav-layout.ts): `offset` cells
    left of the band's end line (--c-end), on `row`. */
export interface LocalePlacement {
  offset: number;
  row: number;
}

/** One GridRadioButtons option's placement (lib/radio-layout.ts): the
    indicator cell at `col`, its label in the `span` cells right of it. */
export interface RadioPlacement {
  col: number;
  span: number;
  row: number;
}

/** Where a GridRadioButtons group packs its options (lib/radio-layout.ts). */
export interface RadioGeometry {
  startCol: number;   // column the first indicator sits on
  bandEnd: number;    // exclusive end line of the band
  baseRow: number;    // first row
  vertical: boolean;  // one option per row (every other row) vs inline flow
}

/** The page grid at one container width (lib/grid-geometry.ts). */
export interface GridGeometry {
  fontSize: number;   // px; the grid's text size in this layout mode
  cell: number;       // px; square cell side (fractional when narrow)
  gridCols: number;   // whole columns that fit
  bandCells: number;  // content band width, in cells
  colStart: number;   // 1-based first column of the band
  filmCols: number;   // film masonry columns (1–3)
  filmWidth: number;  // film card width, in cells
}

/** CSS custom property declarations, name → value. */
export type CssDecls = Record<string, string>;

/** A layout value as a function of the container width (lib/step-table.ts). */
export type StepFn = (width: number, narrow: boolean) => CssDecls;

/** One layout mode's sweep: the value at the range start, then each change. */
export interface StepSweep {
  base: CssDecls;
  steps: { minWidth: number; decls: CssDecls }[];
}

/** A step function swept over both layout modes (lib/step-table.ts). */
export interface StepTable {
  narrow: StepSweep;
  wide: StepSweep;
}

/** A label's advance width at font-size 1px (lib/text-metrics.ts), and whether
    the bundled font has every glyph (else the width is an estimate and the
    client re-measures it in whatever font the browser picked). */
export interface TextMeasure {
  em: number;
  covered: boolean;
}

/** A page's build-time price column fit (lib/price-css.ts). */
export interface PricePageFit {
  priceCells: number; // desktop --price-cells
  coveredEm: number;  // widest price the bundled font fully covers, in em
  css: string;        // narrow per-width --pw<key> step table
}

/** The slice of Document lib/page-lifecycle.ts needs (tests pass a stand-in):
    the current body (a client navigation replaces it) and its events. */
export interface PageDoc {
  readonly body: object | null;
  addEventListener(type: string, listener: () => void): void;
}
