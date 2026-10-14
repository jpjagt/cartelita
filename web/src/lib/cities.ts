import type { CityConfig, Locale } from "@/lib/types";

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
  asuncion: {
    slug: "asuncion",
    name: "Asunción",
    locales: ["es", "en"],
    defaultLocale: "es",
    // Asunción's sources are mostly cinemas and cultural centres' film cycles.
    defaultList: "film",
    // Paraguay has been on permanent UTC−3 (no DST) since October 2024.
    timezone: "America/Asuncion",
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

/** Where the city selector sends a visitor reading `list` in `locale`:
    `target` in the same locale when it serves it (else its default locale),
    on the same list when it has one by that slug (My list always exists),
    else its default list. `targetLists` are the target city's list slugs. */
export function cityHref(target: CityConfig, locale: Locale, list: string, targetLists: string[]): string {
  const lc = target.locales.includes(locale) ? locale : target.defaultLocale;
  const slug = list === MY_LIST || targetLists.includes(list) ? list : target.defaultList;
  return `/${target.slug}/${lc}/${slug}`;
}

/** Query flag on `/` that shows the city picker instead of redirecting to the
    last visited city (the city selector's "All cities"). */
export const PICK_PARAM = "pick";

/** localStorage key holding the last visited city page's prefix
    (`/<city>/<locale>/`), where `/` redirects to. */
export const LAST_CITY_KEY = "cartelita-last-city";
