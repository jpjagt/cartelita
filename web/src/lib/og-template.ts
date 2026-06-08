import type { Locale } from "@/lib/types";
import { categoryName } from "@/i18n";
import { t } from "@/i18n";

export interface OgNavItem {
  slug: string | null; // null for the "and more" pseudo-item
  label: string;
  active: boolean;
}

const FIXED_GENRES = ["jazz", "classic", "theater", "film"];

/** DB list slug → i18n category key. The list slug is `classic`; the i18n key is `classical`. */
export function slugForName(slug: string): string {
  return slug === "classic" ? "classical" : slug;
}

/**
 * OG genre nav: active genre first, then the fixed four minus the active one,
 * skipping any slug not in `lists` (real DB lists), then the localized "and more".
 */
export function ogGenreNav(
  locale: Locale,
  active: string,
  lists: string[],
): OgNavItem[] {
  const item = (slug: string, isActive: boolean): OgNavItem => ({
    slug,
    label: categoryName(locale, slugForName(slug)),
    active: isActive,
  });
  const others = FIXED_GENRES.filter(
    (s) => s !== active && lists.includes(s),
  ).map((s) => item(s, false));
  const nav: OgNavItem[] = [item(active, true), ...others];
  nav.push({ slug: null, label: t(locale).andMore, active: false });
  return nav;
}
