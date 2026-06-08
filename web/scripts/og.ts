import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { chromium } from "playwright";
import { LOCALES } from "@/lib/types";
import { getCategoryLists, getEventsForList } from "@/lib/queries";
import { groupEventsByDay } from "@/lib/agenda";
import { renderOgHtml } from "@/lib/og-template";

const OUT_DIR = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "dist",
  "og",
);

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const lists = (await getCategoryLists()).map((l) => l.slug);

  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({
      viewport: { width: 1200, height: 630 },
      deviceScaleFactor: 2,
    });
    for (const locale of LOCALES) {
      for (const list of lists) {
        const events = await getEventsForList(list, locale);
        const days = groupEventsByDay(events);
        const html = renderOgHtml({ locale, list, lists, days });
        await page.setContent(html, { waitUntil: "load" });
        // Wait for the inlined webfont to finish loading before measuring text
        // widths (below) or screenshotting — otherwise the nav is laid out with
        // fallback metrics and the PNG can render in the wrong font.
        await page.evaluate(() => document.fonts.ready);
        // Place the genre nav on the grid: each item spans a whole number of
        // cells fitting its text and flows right from col 12 on row 3 — the
        // same `spanOf` logic the live navbar runs at runtime (Navbar.astro).
        // Done here, in the browser, because the template string can't measure
        // text width and the real font metrics only exist after setContent.
        await page.evaluate(() => {
          const cell = 1200 / 26;
          const navStart = 12; // right after the 11-col wordmark
          const items = document.querySelectorAll<HTMLElement>("[data-navitem]");
          let col = navStart;
          for (const a of items) {
            const text = a.querySelector<HTMLElement>(".navitem-text") ?? a;
            const span = Math.max(1, Math.ceil((text.scrollWidth + 6) / cell));
            a.style.gridColumn = `${col} / span ${span}`;
            a.style.gridRow = "3";
            col += span;
          }
        });
        const out = join(OUT_DIR, `${locale}-${list}.png`);
        await page.screenshot({ path: out });
        console.log(`wrote ${out}`);
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
