import type { CityConfig, Locale, PageAlternate, PageMeta } from "@/lib/types";
import { CITIES, cityName, cityNameIn, MY_LIST, TODAY } from "@/lib/cities";
import { categoryName, fill, localeTag, longDate, t } from "@/i18n";

// Every page's <head> metadata, built in one place so a shared link always
// says which city, which list (or day) and that it's Cartelita — in the
// page's own language. Pure: Layout.astro renders whatever these return.

const SITE = "Cartelita";

/** The OG image of the bare / city picker (and the 404 page). */
export const SITE_OG_IMAGE = "/og/cartelita.png";

/** The OG image path of a city page; `slug` is a list slug, today or my-list
    (scripts/og.ts writes exactly these). */
export function ogImagePath(city: string, locale: Locale, slug: string): string {
  return `/og/${city}-${locale}-${slug}.png`;
}

/** og:locale value (language_TERRITORY) for a locale. */
export function ogLocale(locale: Locale): string {
  return localeTag(locale).replace("-", "_");
}

/** "{page} in {city}" in the locale's grammar: "Theater in London",
    "Jazz a Barcelona", "Ջազ Երևանում", "Джаз в Ереване". */
export function inCity(city: CityConfig, locale: Locale, page: string): string {
  return fill(t(locale).inCity, { page, city: cityNameIn(city, locale) });
}

/** The page at `/:city/<lc>/<slug>` in each of the city's locales, plus
    x-default → its default locale. */
export function cityAlternates(city: CityConfig, slug: string): PageAlternate[] {
  return [
    ...city.locales.map((lc) => ({ hreflang: lc, path: `/${city.slug}/${lc}/${slug}` })),
    { hreflang: "x-default", path: `/${city.slug}/${city.defaultLocale}/${slug}` },
  ];
}

const withSite = (title: string) => `${title} — ${SITE}`;

/** A category list page: "Theater in London — Cartelita". */
export function listMeta(city: CityConfig, locale: Locale, list: string): PageMeta {
  const phrase = inCity(city, locale, categoryName(locale, list));
  return {
    title: withSite(phrase),
    description: fill(t(locale).pageDescription, { title: phrase }),
    canonical: `/${city.slug}/${locale}/${list}`,
    ogImage: ogImagePath(city.slug, locale, list),
    ogImageAlt: withSite(phrase),
    alternates: cityAlternates(city, list),
  };
}

/** The Today page: "Today in London — Cartelita". The tab title stays
    dateless (the page heals to the right day client-side after a missed
    build); the description and image carry the build's `date`. */
export function todayMeta(city: CityConfig, locale: Locale, date: string): PageMeta {
  const phrase = inCity(city, locale, t(locale).today);
  const dated = `${phrase}, ${longDate(locale, date)}`;
  return {
    title: withSite(phrase),
    description: fill(t(locale).pageDescription, { title: dated }),
    canonical: `/${city.slug}/${locale}/${TODAY}`,
    ogImage: ogImagePath(city.slug, locale, TODAY),
    ogImageAlt: withSite(dated),
    alternates: cityAlternates(city, TODAY),
  };
}

/** My list: "My list · London — Cartelita". */
export function myListMeta(city: CityConfig, locale: Locale): PageMeta {
  const strings = t(locale);
  const phrase = `${strings.myList} · ${cityName(city, locale)}`;
  return {
    title: withSite(phrase),
    description: fill(strings.myListDescription, { city: cityNameIn(city, locale) }),
    canonical: `/${city.slug}/${locale}/${MY_LIST}`,
    ogImage: ogImagePath(city.slug, locale, MY_LIST),
    ogImageAlt: withSite(phrase),
    alternates: cityAlternates(city, MY_LIST),
  };
}

/** Every city, as a list in `locale` ("Barcelona, Yerevan … and London"). */
export function cityList(locale: Locale): string {
  const names = Object.values(CITIES).map((c) => cityName(c, locale));
  return new Intl.ListFormat(localeTag(locale), { type: "conjunction" }).format(names);
}

/** The bare / city picker. */
export function pickerMeta(locale: Locale = "en"): PageMeta {
  const strings = t(locale);
  const title = `${SITE} — ${strings.tagline}`;
  return {
    title,
    description: fill(strings.pickerDescription, { cities: cityList(locale) }),
    canonical: "/",
    ogImage: SITE_OG_IMAGE,
    ogImageAlt: title,
    alternates: [],
  };
}

/** The 404 page: not indexed, no canonical; shares as the home page. */
export function notFoundMeta(locale: Locale = "en"): PageMeta {
  const strings = t(locale);
  return {
    title: withSite(strings.notFound),
    description: fill(strings.pickerDescription, { cities: cityList(locale) }),
    url: "/",
    ogImage: SITE_OG_IMAGE,
    ogImageAlt: `${SITE} — ${strings.tagline}`,
    alternates: [],
    noindex: true,
  };
}
