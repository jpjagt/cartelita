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
    center: [2.1734, 41.3851],
  },
  yerevan: {
    slug: "yerevan",
    name: "Yerevan",
    locales: ["hy", "ru", "en"],
    defaultLocale: "hy",
    defaultList: "jazz",
    timezone: "Asia/Yerevan",
    center: [44.5152, 40.1872],
  },
  amsterdam: {
    slug: "amsterdam",
    name: "Amsterdam",
    locales: ["nl", "en"],
    defaultLocale: "nl",
    defaultList: "jazz",
    timezone: "Europe/Amsterdam",
    center: [4.9041, 52.3676],
  },
  rotterdam: {
    slug: "rotterdam",
    name: "Rotterdam",
    locales: ["nl", "en"],
    defaultLocale: "nl",
    defaultList: "jazz",
    timezone: "Europe/Amsterdam",
    center: [4.4777, 51.9244],
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
    center: [5.1214, 52.0907],
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
    center: [-57.5759, -25.2637],
  },
  london: {
    slug: "london",
    name: "London",
    locales: ["en"],
    defaultLocale: "en",
    // London's deepest category: the subsidised / new-writing theatre scene.
    defaultList: "theater",
    timezone: "Europe/London",
    center: [-0.1278, 51.5074],
    // The cinemas come from Clusterflick's open data (MIT; scraper/…/clusterflick_SOURCE.md).
    listCredits: { film: { name: "Clusterflick", url: "https://clusterflick.com" } },
  },
};

// Slug of the per-visitor favourites page, /:city/:locale/my-list. Lives beside
// the category list routes, so no cartelera list may use this slug.
export const MY_LIST = "my-list";

// Slug of the city's Today page, /:city/:locale/today (lib/today.ts). Same
// rule: no cartelera list may use it.
export const TODAY = "today";

/** Page slugs living beside the list routes; a list with one of these slugs
    would collide with the page (the list route refuses to build it). */
export const RESERVED_LIST_SLUGS: readonly string[] = [MY_LIST, TODAY];

export const CITY_SLUGS = Object.keys(CITIES);

export function cityConfig(slug: string): CityConfig {
  const city = CITIES[slug];
  if (!city) throw new Error(`unknown city slug ${JSON.stringify(slug)}`);
  return city;
}

/** Where the city selector sends a visitor reading `list` in `locale`:
    `target` in the same locale when it serves it (else its default locale),
    on the same list when it has one by that slug (My list and Today always
    exist),
    else its default list. `targetLists` are the target city's list slugs. */
export function cityHref(target: CityConfig, locale: Locale, list: string, targetLists: string[]): string {
  const lc = target.locales.includes(locale) ? locale : target.defaultLocale;
  const slug = RESERVED_LIST_SLUGS.includes(list) || targetLists.includes(list) ? list : target.defaultList;
  return `/${target.slug}/${lc}/${slug}`;
}

/** Query flag on `/` that shows the city picker instead of redirecting to the
    last visited city (the city selector's "All cities"). */
export const PICK_PARAM = "pick";

/** localStorage key holding the last visited city page's prefix
    (`/<city>/<locale>/`), where `/` redirects to. */
export const LAST_CITY_KEY = "cartelita-last-city";
