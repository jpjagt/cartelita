import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import type { Locale } from "@/lib/types";
import { categoryName } from "@/i18n";
import { t } from "@/i18n";

// The OG image is set in the same Helvetica clone as the live site (TeX Gyre
// Heros). The live site loads it from /fonts via @font-face, but Playwright
// renders this template with page.setContent(), which has NO base URL — a
// relative font URL would never resolve. So we read the woff2 from public/
// and inline it as a base64 data: URI. Read once at module load (the script
// renders many pages). Keep this stack + font in sync with global.css. */
const FONTS_DIR = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "public",
  "fonts",
);
function fontDataUri(file: string): string {
  const b64 = readFileSync(join(FONTS_DIR, file)).toString("base64");
  return `data:font/woff2;base64,${b64}`;
}
const FONT_FACE_CSS = `
@font-face {
  font-family: "TeX Gyre Heros";
  src: url("${fontDataUri("TeXGyreHeros-Regular.woff2")}") format("woff2");
  font-weight: 400; font-style: normal;
}
@font-face {
  font-family: "TeX Gyre Heros";
  src: url("${fontDataUri("TeXGyreHeros-Bold.woff2")}") format("woff2");
  font-weight: 700; font-style: normal;
}`;

export interface OgNavItem {
  slug: string | null; // null for the "and more" pseudo-item
  label: string;
  active: boolean;
}

// Fixed display order for the OG genre nav (slug = DB list slug). The active
// list keeps its colored fill wherever it lands; it is NOT hoisted to the front.
const FIXED_GENRES = ["jazz", "theater", "classic", "film"];

/** DB list slug → i18n category key. The list slug is `classic`; the i18n key is `classical`. */
export function slugForName(slug: string): string {
  return slug === "classic" ? "classical" : slug;
}

/**
 * OG genre nav, in fixed order: the four FIXED_GENRES that are real DB `lists`,
 * then the active list IF it isn't one of those four (appended as the `[x]`
 * "other" slot), then the localized "and more". The active item keeps its
 * genre-colored fill regardless of position.
 */
export function ogGenreNav(
  locale: Locale,
  active: string,
  lists: string[],
): OgNavItem[] {
  const item = (slug: string): OgNavItem => ({
    slug,
    label: categoryName(locale, slugForName(slug)),
    active: slug === active,
  });
  const fixed = FIXED_GENRES.filter((s) => lists.includes(s)).map(item);
  const nav: OgNavItem[] = [...fixed];
  // Append the active list as the `[x]` other-genre slot only when it isn't
  // already shown among the fixed four.
  if (!FIXED_GENRES.includes(active)) {
    nav.push(item(active));
  }
  nav.push({ slug: null, label: t(locale).andMore, active: false });
  return nav;
}

import type { AgendaDay } from "@/lib/types";
import { localeTag } from "@/i18n";

interface RenderOgArgs {
  locale: Locale;
  list: string;
  lists: string[];
  days: AgendaDay[];
}

// Light palette values mirrored from :root in global.css (oklch renders
// identically in Chromium). Background white, near-black foreground, grey
// muted text, and a light grey grid line. The day-header band uses a slightly
// darker grey than the grid line so it reads as a shaded row on white.
const BG = "oklch(1 0 0)";
const FG = "oklch(0.145 0 0)";
const MUTED_FG = "oklch(0.556 0 0)";
const MUTED_BG = "oklch(0.97 0 0)";
const GRID_LINE = "oklch(0.922 0 0)";

// Genre fill colors (mirrored from [data-genre] rules in global.css).
const GENRE_COLORS: Record<string, { primary: string; text: string }> = {
  jazz: { primary: "#d3000e", text: "#ffffff" },
  flamenco: { primary: "#d3000e", text: "#ffffff" },
  film: { primary: "#d3000e", text: "#ffffff" },
  classic: { primary: "#0a00cc", text: "#ffffff" },
  classical: { primary: "#0a00cc", text: "#ffffff" },
  theater: { primary: "#2d6c49", text: "#ffffff" },
  dance: { primary: "#2d6c49", text: "#ffffff" },
  pop: { primary: "#f5c449", text: "#000000" },
};

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function dayHeading(locale: Locale, date: string): string {
  return new Date(date + "T00:00:00").toLocaleDateString(localeTag(locale), {
    weekday: "long", day: "numeric", month: "long",
  });
}

export function renderOgHtml({ locale, list, lists, days }: RenderOgArgs): string {
  const strings = t(locale);
  const nav = ogGenreNav(locale, list, lists);

  // Cell ≈ 1200 / 26. Rows are the same square height.
  const cell = 1200 / 26;

  // Header: wordmark on the left, genre nav on the wordmark's baseline row. The
  // wordmark spans cols 1–11 / 3 rows (matching the live site); the nav items
  // sit on row 3, flowing right from col 12. Each item is placed in its own
  // grid columns, sized to a WHOLE number of cells fitting its text — exactly
  // like the live navbar's `spanOf` logic — so the tabs land on gridlines. The
  // template can't measure text width (it's a pure string), so each item is
  // emitted with only its colors and a `data-navitem` marker; og.ts measures
  // and assigns grid-column/-row in the browser after setContent (where the
  // real font metrics live, matching the live nav's runtime measurement).
  const navItems = nav
    .map((n) => {
      const c = n.slug ? GENRE_COLORS[n.slug] : undefined;
      const style = n.active && c
        ? `background:${c.primary};color:${c.text};`
        : `color:${MUTED_FG};`;
      return `<span class="cell navitem" data-navitem style="${style}"><span class="navitem-text">${esc(n.label)}</span></span>`;
    })
    .join("");
  const navHtml = navItems;

  const rows: string[] = [];
  let gridRow = 4; // rows 1-3 = header (3-row wordmark + nav on row 3)

  for (const day of days) {
    rows.push(
      `<div class="cell day" style="grid-row:${gridRow};grid-column:1/-1;background:${MUTED_BG};color:${FG};">${esc(
        dayHeading(locale, day.date),
      )}</div>`,
    );
    gridRow++;
    for (const e of day.events) {
      const price = e.price ? (strings.prices[e.price] ?? e.price) : "";
      rows.push(
        `<div class="cell" style="grid-row:${gridRow};grid-column:1/span 2;color:${MUTED_FG};">${esc(
          e.startTime ?? "",
        )}</div>` +
          `<div class="cell ellip" style="grid-row:${gridRow};grid-column:3/-9;color:${FG};">${esc(
            e.title,
          )}</div>` +
          `<div class="cell right ellip" style="grid-row:${gridRow};grid-column:-9/span 6;color:${FG};">${esc(
            e.venueName,
          )}</div>` +
          `<div class="cell right" style="grid-row:${gridRow};grid-column:-3/span 2;color:${MUTED_FG};">${esc(
            price,
          )}</div>`,
      );
      gridRow++;
    }
    gridRow++; // blank spacer row after each day
  }

  if (days.length === 0) {
    rows.push(
      `<div class="cell" style="grid-row:${gridRow};grid-column:1/-1;color:${MUTED_FG};">${esc(
        strings.noEvents,
      )}</div>`,
    );
  }

  return `<!DOCTYPE html>
<html lang="${locale}"><head><meta charset="utf-8"><style>
${FONT_FACE_CSS}
* { margin:0; padding:0; box-sizing:border-box; }
html,body { width:1200px; height:630px; }
body {
  background:${BG}; color:${FG}; overflow:hidden;
  font-family:"Helvetica Neue", Helvetica, "TeX Gyre Heros", Arial, sans-serif;
  font-size:${Math.round(cell * 0.56)}px;
  display:grid;
  grid-template-columns:repeat(26, ${cell}px);
  grid-auto-rows:${cell}px;
  background-image:
    linear-gradient(to right, ${GRID_LINE} 2px, transparent 2px),
    linear-gradient(to bottom, ${GRID_LINE} 2px, transparent 2px);
  background-size:${cell}px ${cell}px;
}
.cell {
  display:flex; align-items:flex-end; justify-content:flex-start;
  padding:0 4px 2px 4px; min-width:0; overflow:hidden; white-space:nowrap; line-height:1;
}
.cell.right { justify-content:flex-end; text-align:right; }
.cell.ellip { text-overflow:ellipsis; }
/* Genre nav items: each is its own grid cell (placed by og.ts), bottom-left
   aligned and sized to a whole number of cells fitting its text. */
.navitem { overflow:hidden; white-space:nowrap; }
.navitem-text {
  display:block; max-width:100%; overflow:hidden; white-space:nowrap;
  text-overflow:ellipsis;
}
/* Wordmark: 11 cols × 3 rows, font 2.6× the cell, bottom-left aligned. Mirrors
   .navbar-wordmark from global.css, including the 'r' kerning fix and the
   margin-left:-3px / line-height:0.78 baseline tuning. */
.wordmark {
  grid-row:1 / span 3; grid-column:1 / span 11;
  font-weight:600; color:${FG};
  align-items:flex-end; overflow:visible;
}
.wordmark .wordmark-text {
  font-size:${Math.round(cell * 2.6)}px; line-height:0.78; margin-left:-3px;
  white-space:nowrap;
}
.day { font-weight:500; }
</style></head>
<body>
<div class="cell wordmark"><span class="wordmark-text">Ca<span style="margin-right:2px">r</span>telita</span></div>
${navHtml}
${rows.join("\n")}
</body></html>`;
}
