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
