export type Locale = "ca" | "es" | "en";
export const LOCALES: Locale[] = ["ca", "es", "en"];
export const DEFAULT_LOCALE: Locale = "es";

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
