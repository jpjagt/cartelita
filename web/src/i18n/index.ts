import type { Locale } from "@/lib/types";

interface Strings {
  siteTitle: string;
  noEvents: string;
  back: string;
  // category names keyed by category slug
  categories: Record<string, string>;
}

const DICT: Record<Locale, Strings> = {
  ca: {
    siteTitle: "Cartelera Barcelona",
    noEvents: "No hi ha esdeveniments propers.",
    back: "Inici",
    categories: { film: "Cinema", jazz: "Jazz", classical: "Clàssica", theater: "Teatre" },
  },
  es: {
    siteTitle: "Cartelera Barcelona",
    noEvents: "No hay eventos próximos.",
    back: "Inicio",
    categories: { film: "Cine", jazz: "Jazz", classical: "Clásica", theater: "Teatro" },
  },
  en: {
    siteTitle: "Cartelera Barcelona",
    noEvents: "No upcoming events.",
    back: "Home",
    categories: { film: "Film", jazz: "Jazz", classical: "Classical", theater: "Theater" },
  },
};

export function t(locale: Locale): Strings {
  return DICT[locale];
}

export function categoryName(locale: Locale, slug: string): string {
  return DICT[locale].categories[slug] ?? slug;
}

/** BCP-47 tag for Intl/date formatting. */
export function localeTag(locale: Locale): string {
  return { ca: "ca-ES", es: "es-ES", en: "en-GB" }[locale];
}
