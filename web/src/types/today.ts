import type { CityAgendaEvent } from "@/lib/types";
import type { ViewSwitch } from "@/lib/view-switch";

// Types for the Today page (/:city/:locale/today): lib/today.ts (pure rules),
// lib/today-map.ts (the lazily loaded map) and lib/map-style.ts.

/** A city-wide event as the Today page ships it: the My list agenda event
    plus what the client needs to decide, minute by minute, whether it still
    shows (its end, if known) and which genres it belongs to (every list it
    is curated in — an event in several lists appears once). */
export interface TodayEvent extends CityAgendaEvent {
  /** Every cartelera list (genre) of the city that shows this event. */
  lists: string[];
  endDate: string | null; // ISO yyyy-mm-dd
  endTime: string | null; // 'HH:MM'
  /** The event has several start_times (film screenings): each screening
      gets the start + 2h rule, the event's single end is ignored. */
  multi: boolean;
}

/** One event's client-side data, keyed by event id in the page's JSON (the
    showtimes of one event share it). Short keys: it ships for 3 days of a
    whole city. */
export interface TodayEventMeta {
  t: string; // title
  u: string; // source URL
  p: string; // display price ("" when none)
  g: string; // tint genre (navbar's busiest of its lists)
  l: string[]; // every list it is in
  ed: string | null; // end date
  et: string | null; // end time
  m: boolean; // multi-showtime
}

/** A venue the page's events happen at; lat/lng null until geocoded. */
export interface TodayVenue {
  n: string; // name
  lat: number | null;
  lng: number | null;
}

/** The wall clock in a city's time zone. */
export interface WallClock {
  date: string; // yyyy-mm-dd
  time: string; // HH:MM (24h)
}

/** What the remaining-today rule needs of one row (one showtime). */
export interface RemainingInput {
  date: string; // the showtime's real calendar date
  time: string | null; // null / "" = all-day or unknown: always remains
  endDate: string | null;
  endTime: string | null;
  multi: boolean;
}

/** syncAgenda's notion of "now" (Layout.astro), in the agenda's logical-day
    frame (05:00 boundary): the logical date and timeSortKey-ordered keys for
    now and for two hours ago. */
export interface AgendaClock {
  logicalDate: string;
  nowKey: string;
  cutoffKey: string;
}

/** One still-visible event at a venue, for the map panel. */
export interface MapItem {
  id: string;
  time: string; // "" when unknown
  title: string;
  url: string;
  price: string;
  genre: string;
}

/** A venue with visible events today, as the map shows it. */
export interface MapVenue {
  slug: string;
  name: string;
  lat: number;
  lng: number;
  genre: string; // tint of its first event
  items: MapItem[];
}

/** The map's venues, plus how many venues with visible events have no
    coordinates (left off the map, noted under it). */
export interface MapVenues {
  venues: MapVenue[];
  missing: number;
}

/** A visible row as the map grouping reads it. */
export interface VisibleRow {
  id: string;
  venue: string;
  time: string;
}

/** Colours the basemap is repainted with: `ink(t)` mixes the page background
    (t = 0) toward the foreground (t = 1), so one rule serves light and dark. */
export interface MapPalette {
  ink: (t: number, alpha?: number) => string;
}

/** The handle the Today page keeps on its (lazily created) map. */
export interface TodayMapHandle {
  update(data: MapVenues): void;
  select(slug: string | null): void;
  resize(): void;
  destroy(): void;
}

/** Options for creating the map. */
export interface TodayMapOptions {
  container: HTMLElement;
  /** Fallback centre [lng, lat] when no venue has coordinates. */
  center: [number, number];
  onSelect: (slug: string | null) => void;
}

/** A MapLibre style document, loosely typed (only what the recolour reads). */
export interface StyleDoc {
  version: number;
  layers: StyleLayer[];
  [key: string]: unknown;
}

export interface StyleLayer {
  id: string;
  type: string;
  source?: string;
  "source-layer"?: string;
  paint?: Record<string, unknown>;
  layout?: Record<string, unknown>;
  [key: string]: unknown;
}

/** The Today page script's state for the page currently shown. */
export interface TodayPage {
  root: HTMLElement;
  city: string;
  tz: string;
  center: [number, number];
  /** Genre options in navbar order. */
  order: string[];
  events: Record<string, TodayEventMeta>;
  venues: Record<string, TodayVenue>;
  /** The remembered genre selection (may hold genres not offered today). */
  selection: string[];
  views: ViewSwitch | null;
  timer: number;
  map: TodayMapHandle | null;
  mapLoading: boolean;
  selected: string | null;
  lastMap: MapVenues;
}
