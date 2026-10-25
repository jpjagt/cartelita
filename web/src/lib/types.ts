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
  /** [lng, lat] the Today map centres on when no venue has coordinates. */
  center: [number, number];
  /** Lists fed (wholly or mostly) by a third-party aggregator whose terms ask
      for credit: list slug → the credit shown under that list. */
  listCredits?: Record<string, ListCredit>;
}

/** "Listings via <name>" under a list (CityConfig.listCredits). */
export interface ListCredit {
  name: string;
  url: string;
}

/** One option in a GridRadioButtons control. */
export interface GridRadioOption {
  value: string;
  label: string;
}

export interface CategoryList {
  slug: string;        // also the category slug, used for name translation
  /** Events in the next NAV_WINDOW_DAYS (lib/genre-nav.ts): orders the city's
      genre tabs and decides which go behind "More". */
  upcoming: number;
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
  | "chevron"
  | "close";

/** Where one agenda row lands (lib/event-panel.ts): its 0-based index (--ev)
    and the extra grid rows open event panels push in above it (--po). */
export interface RowNumbering {
  ev: number;
  po: number;
}

/** One navbar item's grid placement (lib/nav-layout.ts): first column line,
    whole cells spanned, row. */
export interface NavPlacement {
  col: number;
  span: number;
  row: number;
}

/** One run of navbar cells the tabs may flow along: `row`, columns
    [start, end) (end exclusive). */
export interface NavLine {
  row: number;
  start: number;
  end: number;
}

/** A navbar dropdown (More, city): its first column, the row of its trigger
    (the menu's top edge is that row's bottom gridline), its width in cells. */
export interface NavMenuPlacement {
  col: number;
  row: number;
  width: number;
}

/** What the navbar lays out, as label advances at font-size 1px
    (lib/text-metrics.ts; the client re-measures labels the bundled font
    can't cover). lib/nav-layout.ts turns it into placements per grid. */
export interface NavModel {
  /** Genre tab labels, in tab (volume) order. */
  genres: number[];
  /** How many leading genres qualify for a tab (lib/genre-nav.ts
      tabbableCount); the rest always go behind More. */
  tabbable: number;
  /** How many leading genres may ever get a tab (lib/genre-nav.ts
      topLevelCount, TOP_LEVEL_GENRES); the rest are always in More, even
      when a lone one would fit as a tab. */
  topLevel: number;
  /** Index into `genres` of the page's own genre; -1 when it isn't one. */
  active: number;
  /** The "More" trigger label. */
  more: number;
  /** The set-apart tabs after the genres: Film (when the city has it), My list. */
  fixed: number[];
  /** The current city's name (the city selector trigger). */
  city: number;
  /** The city dropdown's entries: every city, then "All cities". */
  cityMenu: number[];
  /** Locale switcher cells. */
  localeCount: number;
}

/** A NavModel in whole cells at one grid (lib/nav-layout.ts navSpans): every
    label's span; the triggers' include their chevron cell. */
export interface NavSpans {
  genres: number[];
  tabbable: number;
  topLevel: number;
  active: number;
  more: number;
  /** The More trigger when it shows the active genre's name instead. */
  activeMore: number;
  fixed: number[];
  city: number;
  cityMenu: number[];
  localeCount: number;
}

/** Tab-row items flowed onto their lines (lib/nav-layout.ts flowLines). */
export interface NavFlow {
  flow: NavPlacement[];
  fixed: NavPlacement[];
}

/** A tab-row fit: `k` genre tabs shown; genres [k, n) are in More. */
export interface NavFit extends NavFlow {
  k: number;
}

/** The navbar at one grid (lib/nav-layout.ts layoutNav). */
export interface NavLayout {
  /** Per genre: its tab, or null when it sits in the More dropdown. */
  tabs: (NavPlacement | null)[];
  /** The More trigger (label + chevron cell); null when nothing is in More. */
  more: NavPlacement | null;
  /** The More dropdown; one row per genre in it, in order. */
  moreMenu: NavMenuPlacement | null;
  /** Whether the More trigger shows the active genre's name (it's in More). */
  moreShowsActive: boolean;
  fixed: NavPlacement[];
  /** The city selector trigger (name + chevron cell). */
  city: NavPlacement;
  cityMenu: NavMenuPlacement;
  /** One cell each. */
  locales: NavPlacement[];
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

/** One analytics event's properties (Umami event data): low-cardinality
    strings and small numbers only — never titles or free text
    (docs/analytics.md). */
export type AnalyticsData = Record<string, string | number | boolean>;

/** Where a page sits in the site, read off its path (lib/analytics.ts
    pageOfPath): "" for a part the path doesn't have (the bare / city picker
    has no city, locale or list). */
export interface PageRef {
  city: string;
  locale: string;
  list: string;
}

/** One navigation's analytics event (lib/analytics.ts navEvent). */
export interface NavEvent {
  name: "city_switch" | "locale_switch" | "nav_tab";
  data: AnalyticsData;
}
