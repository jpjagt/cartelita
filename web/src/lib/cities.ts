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
  },
  yerevan: {
    slug: "yerevan",
    name: "Yerevan",
    locales: ["hy", "ru", "en"],
    defaultLocale: "hy",
    defaultList: "jazz",
  },
};

export const CITY_SLUGS = Object.keys(CITIES);

export function cityConfig(slug: string): CityConfig {
  const city = CITIES[slug];
  if (!city) throw new Error(`unknown city slug ${JSON.stringify(slug)}`);
  return city;
}
