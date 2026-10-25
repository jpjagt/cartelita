import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import type { CategoryList, Locale, OgImageSpec, OgNavItem } from "@/lib/types";
import { categoryName, longDate, t } from "@/i18n";
import { MY_LIST, TODAY } from "@/lib/cities";
import { FILM_LIST, navOrder, tabbableCount } from "@/lib/genre-nav";

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

/** The canvas: 1200×630, 26 square cells across (like the live grid). */
export const OG_COLS = 26;
export const OG_CELL = 1200 / OG_COLS;
/** Header: the wordmark + city on rows 1–3, the nav band on row 4. */
export const OG_NAV_ROW = 4;
const BODY_ROW = OG_NAV_ROW + 1;
/** Rows that fit the canvas (the last one partly). */
const OG_ROWS = Math.ceil(630 / OG_CELL);

/**
 * The OG image's nav band: the city's own navbar, as the live site shows it
 * on a wide screen — the genres that earn a tab (lib/genre-nav.ts: top-level
 * genres by volume), the active page's genre even when it lives in More,
 * "and more", then Today · Film · My list set apart.
 */
export function ogNav(locale: Locale, active: string, lists: CategoryList[]): OgNavItem[] {
  const strings = t(locale);
  const genres = navOrder(
    lists.filter((l) => l.slug !== FILM_LIST && (l.upcoming > 0 || l.slug === active)),
  );
  const shown = genres.slice(0, tabbableCount(genres));
  const activeGenre = genres.find((g) => g.slug === active);
  if (activeGenre && !shown.includes(activeGenre)) shown.push(activeGenre);
  const item = (slug: string, label: string, fixed: boolean): OgNavItem => ({
    slug, label, active: slug === active, fixed,
  });
  return [
    ...shown.map((g) => item(g.slug, categoryName(locale, g.slug), false)),
    // Always: the band is a teaser, there is more on the site (and More
    // holds the quieter genres).
    { slug: null, label: strings.andMore, active: false, fixed: false },
    item(TODAY, strings.today, true),
    ...(lists.some((l) => l.slug === FILM_LIST)
      ? [item(FILM_LIST, categoryName(locale, FILM_LIST), true)]
      : []),
    item(MY_LIST, strings.myList, true),
  ];
}

/**
 * Place the nav band on the grid. `spans` are each item's whole-cell widths
 * (measured in the browser, scripts/og.ts — like the live navbar's spanOf).
 * Genres + "and more" flow right from column 1; the fixed tabs sit flush
 * against the right edge, at least one empty cell after the genres. When it
 * doesn't fit, inactive genres are dropped from the end ("and more" stays).
 * Returns each item's 1-based start column, or null when it's left out.
 */
export function placeNav(items: OgNavItem[], spans: number[], cols = OG_COLS): (number | null)[] {
  const keep = items.map(() => true);
  const width = (fixed: boolean) =>
    items.reduce((w, n, i) => w + (keep[i] && n.fixed === fixed ? spans[i] : 0), 0);
  const fixedWidth = width(true);
  while (width(false) + 1 + fixedWidth > cols) {
    let victim = -1;
    items.forEach((n, i) => {
      if (keep[i] && !n.fixed && !n.active && n.slug !== null) victim = i;
    });
    if (victim < 0) break;
    keep[victim] = false;
  }
  const placed: (number | null)[] = items.map(() => null);
  let genreCol = 1;
  let fixedCol = cols + 1 - fixedWidth;
  items.forEach((n, i) => {
    if (!keep[i]) return;
    if (n.fixed) {
      placed[i] = fixedCol;
      fixedCol += spans[i];
    } else {
      placed[i] = genreCol;
      genreCol += spans[i];
    }
  });
  return placed;
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

// Genre fill colors (mirrored from [data-genre] rules in global.css); any
// other page (Today, My list, club …) fills with the foreground, as live.
const GENRE_COLORS: Record<string, { primary: string; text: string }> = {
  jazz: { primary: "#d3000e", text: "#ffffff" },
  flamenco: { primary: "#d3000e", text: "#ffffff" },
  film: { primary: "#d3000e", text: "#ffffff" },
  classical: { primary: "#0a00cc", text: "#ffffff" },
  theater: { primary: "#2d6c49", text: "#ffffff" },
  dance: { primary: "#2d6c49", text: "#ffffff" },
  pop: { primary: "#f5c449", text: "#000000" },
};
const DEFAULT_FILL = { primary: FG, text: BG };

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** A grid cell holding one line of text (truncated with an ellipsis). */
function cell(row: number, column: string, text: string, style = "", cls = ""): string {
  return `<div class="cell${cls ? " " + cls : ""}" style="grid-row:${row};grid-column:${column};${style}"><span class="t">${esc(text)}</span></div>`;
}

function band(row: number, text: string): string {
  return cell(row, "1/-1", text, `background:${MUTED_BG};color:${FG};`, "day");
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** The image body's cells, from row BODY_ROW. */
function bodyHtml({ locale, body }: OgImageSpec): string {
  const strings = t(locale);
  const out: string[] = [];
  let row = BODY_ROW;
  if (body.kind === "agenda") {
    for (const day of body.days) {
      if (row > OG_ROWS) break;
      out.push(band(row++, longDate(locale, day.date)));
      for (const e of day.events) {
        if (row > OG_ROWS) break;
        const price = e.price ? (strings.prices[e.price] ?? e.price) : "";
        out.push(
          cell(row, "1/span 2", e.startTime ?? "", `color:${MUTED_FG};`) +
            cell(row, "3/-9", e.title, `color:${FG};`) +
            cell(row, "-9/span 6", e.venueName, `color:${FG};`, "right") +
            cell(row, "-3/span 2", price, `color:${MUTED_FG};`, "right"),
        );
        row++;
      }
      row++; // blank spacer row after each day
    }
    if (body.days.length === 0) out.push(cell(row, "1/-1", strings.noEvents, `color:${MUTED_FG};`));
    return out.join("\n");
  }
  // Names in three columns (cols 1–9, 10–18, 19–26), filled top to bottom.
  const heading = body.kind === "venues" ? body.heading : capitalize(body.heading);
  const names = body.kind === "venues" ? body.venues : body.cities;
  out.push(band(row++, heading));
  row++;
  const perCol = Math.max(1, OG_ROWS - row + 1);
  const colStarts = ["1/span 8", "10/span 8", "19/span 8"];
  names.slice(0, perCol * colStarts.length).forEach((name, i) => {
    out.push(cell(row + (i % perCol), colStarts[Math.floor(i / perCol)], name, `color:${FG};`));
  });
  return out.join("\n");
}

/**
 * The OG image as a standalone HTML document (1200×630, no external
 * resources). Header: the Cartelita wordmark with the city's name beside it
 * at the same size — the first thing a link preview should say — and the
 * city's nav band under it. scripts/og.ts measures the nav labels and places
 * them (placeNav), and shrinks the city name if it doesn't fit.
 */
export function renderOgHtml(spec: OgImageSpec): string {
  const navHtml = spec.nav
    .map((n) => {
      const fill = n.slug ? (GENRE_COLORS[n.slug] ?? DEFAULT_FILL) : undefined;
      const style = n.active && fill
        ? `background:${fill.primary};color:${fill.text};`
        : `color:${MUTED_FG};`;
      return `<div class="cell navitem" data-navitem style="grid-row:${OG_NAV_ROW};${style}"><span class="t">${esc(n.label)}</span></div>`;
    })
    .join("");
  const cityHtml = spec.city
    ? `<div class="cell city" data-city><span class="city-text">${esc(spec.city)}</span></div>`
    : "";

  return `<!DOCTYPE html>
<html lang="${spec.locale}"><head><meta charset="utf-8"><style>
${FONT_FACE_CSS}
* { margin:0; padding:0; box-sizing:border-box; }
html,body { width:1200px; height:630px; }
body {
  background:${BG}; color:${FG}; overflow:hidden;
  font-family:"Helvetica Neue", Helvetica, "TeX Gyre Heros", Arial, sans-serif;
  font-size:${Math.round(OG_CELL * 0.56)}px;
  display:grid;
  grid-template-columns:repeat(${OG_COLS}, ${OG_CELL}px);
  grid-auto-rows:${OG_CELL}px;
  background-image:
    linear-gradient(to right, ${GRID_LINE} 2px, transparent 2px),
    linear-gradient(to bottom, ${GRID_LINE} 2px, transparent 2px);
  background-size:${OG_CELL}px ${OG_CELL}px;
}
.cell {
  display:flex; align-items:flex-end; justify-content:flex-start;
  padding:0 4px 2px 4px; min-width:0; overflow:hidden; white-space:nowrap; line-height:1;
}
/* The text truncates at its end, also when right-aligned. */
.cell .t { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
/* …without clipping descenders (the span's box is one line-height tall). */
.cell .t { padding-bottom:0.2em; margin-bottom:-0.2em; }
.cell.right { justify-content:flex-end; text-align:right; }
/* Wordmark: 11 cols × 3 rows, font 2.6× the cell, bottom-left aligned. Mirrors
   .navbar-wordmark from global.css, including the 'r' kerning fix and the
   margin-left:-3px / line-height:0.78 baseline tuning. */
.wordmark, .city {
  grid-row:1 / span 3; align-items:flex-end; overflow:visible;
}
.wordmark { grid-column:1 / span 11; font-weight:600; color:${FG}; }
.wordmark-text, .city-text {
  font-size:${Math.round(OG_CELL * 2.6)}px; line-height:0.78; white-space:nowrap;
}
.wordmark-text { margin-left:-3px; }
/* The city, on the wordmark's baseline at the same size, in the regular
   weight and muted: the product's name, then where. */
.city { grid-column:12 / -1; color:${MUTED_FG}; font-weight:400; overflow:hidden; }
.day { font-weight:500; }
</style></head>
<body>
<div class="cell wordmark"><span class="wordmark-text">Ca<span style="margin-right:2px">r</span>telita</span></div>
${cityHtml}
${navHtml}
${bodyHtml(spec)}
</body></html>`;
}
