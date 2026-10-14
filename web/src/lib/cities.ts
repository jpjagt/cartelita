import type { CityConfig } from "@/lib/types";

// Every city Cartelita serves. The city is the product scope: it determines
// which locales exist and what the landing list is. The DB `city` table is
// seeded from the scraper side (seed.CITIES); this config is the web-side
// mirror plus the UI-only knobs (locales, defaults) that belong next to the
// i18n dictionaries rather than in Postgres.
export const CITIES: Record<string, CityConfig> = {
  barcelona: {
    slug: "barcelona",
    name: "Barcelona",
    locales: ["ca", "es", "en"],
    defaultLocale: "ca",
    defaultList: "jazz",
    timezone: "Europe/Madrid",
  },
  yerevan: {
    slug: "yerevan",
    name: "Yerevan",
    locales: ["hy", "ru", "en"],
    defaultLocale: "hy",
    defaultList: "jazz",
    timezone: "Asia/Yerevan",
  },
  amsterdam: {
    slug: "amsterdam",
    name: "Amsterdam",
    locales: ["nl", "en"],
    defaultLocale: "nl",
    defaultList: "jazz",
    timezone: "Europe/Amsterdam",
  },
  rotterdam: {
    slug: "rotterdam",
    name: "Rotterdam",
    locales: ["nl", "en"],
    defaultLocale: "nl",
    defaultList: "jazz",
    timezone: "Europe/Amsterdam",
  },
  utrecht: {
    slug: "utrecht",
    name: "Utrecht",
    locales: ["nl", "en"],
    defaultLocale: "nl",
    // Utrecht's jazz scene is thin; its strongest list is pop (TivoliVredenburg,
    // De Helling, EKKO, dB's).
    defaultList: "pop",
    timezone: "Europe/Amsterdam",
  },
};

// Slug of the per-visitor favourites page, /:city/:locale/my-list. Lives beside
// the category list routes, so no cartelera list may use this slug.
export const MY_LIST = "my-list";

export const CITY_SLUGS = Object.keys(CITIES);

export function cityConfig(slug: string): CityConfig {
  const city = CITIES[slug];
  if (!city) throw new Error(`unknown city slug ${JSON.stringify(slug)}`);
  return city;
}
