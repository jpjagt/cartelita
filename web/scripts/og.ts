import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { chromium, type Page } from "playwright";
import { CITIES, cityName, MY_LIST, TODAY } from "@/lib/cities";
import { getCategoryLists, getEventsForList, getTodayAgenda, getVenueDirectory } from "@/lib/queries";
import { groupEventsByDay } from "@/lib/agenda";
import { OG_CELL, ogNav, placeNav, renderOgHtml } from "@/lib/og-template";
import { ogImagePath, SITE_OG_IMAGE } from "@/lib/meta";
import { ogDay } from "@/lib/today";
import { t } from "@/i18n";
import type { OgImageSpec } from "@/lib/types";

// Renders every page's OG image into dist/og/ (paths: lib/meta.ts, which the
// pages' og:image tags use too): each city × locale × list, Today and My
// list, plus the city picker's. Run after `astro build` (nixpacks.toml).

const DIST = join(dirname(fileURLToPath(import.meta.url)), "..", "dist");

async function render(page: Page, spec: OgImageSpec, path: string) {
  await page.setContent(renderOgHtml(spec), { waitUntil: "load" });
  // Wait for the inlined webfont before measuring text or screenshotting —
  // otherwise the nav is laid out with fallback metrics.
  await page.evaluate(() => document.fonts.ready);
  // Each nav item spans a whole number of cells fitting its text (the live
  // navbar's spanOf); the template can't measure, so measure here and place
  // with the pure placeNav.
  const spans = await page.evaluate((cell) => {
    return [...document.querySelectorAll<HTMLElement>("[data-navitem] .t")].map((t) =>
      Math.max(1, Math.ceil((t.scrollWidth + 8) / cell)),
    );
  }, OG_CELL);
  const cols = placeNav(spec.nav, spans);
  await page.evaluate(
    ({ cols, spans }) => {
      document.querySelectorAll<HTMLElement>("[data-navitem]").forEach((el, i) => {
        const col = cols[i];
        if (col === null) el.style.display = "none";
        else el.style.gridColumn = `${col} / span ${spans[i]}`;
      });
      // The city name shares the wordmark's size; a long one shrinks to fit.
      const city = document.querySelector<HTMLElement>("[data-city]");
      const text = city?.querySelector<HTMLElement>(".city-text");
      if (city && text) {
        const room = city.clientWidth - 8;
        if (text.scrollWidth > room) {
          const size = parseFloat(getComputedStyle(text).fontSize);
          text.style.fontSize = `${Math.floor((size * room) / text.scrollWidth)}px`;
        }
      }
    },
    { cols, spans },
  );
  const out = join(DIST, path);
  await page.screenshot({ path: out });
  console.log(`wrote ${out}`);
}

async function main() {
  await mkdir(join(DIST, "og"), { recursive: true });
  const todayAbsolute = new Date().toISOString().slice(0, 10);

  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({
      viewport: { width: 1200, height: 630 },
      deviceScaleFactor: 2,
    });

    // The city picker (/, and the 404 page).
    await render(
      page,
      {
        locale: "en",
        nav: [],
        body: { kind: "cities", heading: t("en").tagline, cities: Object.values(CITIES).map((c) => c.name) },
      },
      SITE_OG_IMAGE,
    );

    for (const city of Object.values(CITIES)) {
      const lists = await getCategoryLists(city.slug);
      const day = ogDay(new Date(), city.timezone);
      const venues = [
        ...new Set((await getVenueDirectory(city.slug)).flatMap((g) => g.venues.map((v) => v.name))),
      ].sort((a, b) => a.localeCompare(b));
      for (const locale of city.locales) {
        const name = cityName(city, locale);
        for (const { slug } of lists) {
          const events = await getEventsForList(city.slug, slug, locale);
          const days = groupEventsByDay(events).filter((d) => d.date >= todayAbsolute);
          await render(
            page,
            { locale, city: name, nav: ogNav(locale, slug, lists), body: { kind: "agenda", days } },
            ogImagePath(city.slug, locale, slug),
          );
        }
        // Today: the build's day in the city (lib/today.ts ogDay).
        const { events } = await getTodayAgenda(city.slug, locale, day, 1);
        await render(
          page,
          {
            locale,
            city: name,
            nav: ogNav(locale, TODAY, lists),
            body: { kind: "agenda", days: groupEventsByDay(events).filter((d) => d.date === day) },
          },
          ogImagePath(city.slug, locale, TODAY),
        );
        // My list: the venue directory it opens on.
        await render(
          page,
          {
            locale,
            city: name,
            nav: ogNav(locale, MY_LIST, lists),
            body: { kind: "venues", heading: t(locale).pickVenues, venues },
          },
          ogImagePath(city.slug, locale, MY_LIST),
        );
      }
    }
  } finally {
    await browser.close();
  }
  // postgres keeps the event loop alive; exit explicitly.
  process.exit(0);
}

main().catch((err) => {
  console.error("OG generation failed:", err);
  process.exit(1);
});
