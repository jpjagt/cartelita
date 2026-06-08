import type { Locale } from "@/lib/types";
import { categoryName } from "@/i18n";
import { t } from "@/i18n";

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
  // wordmark spans cols 1–11 / 3 rows (matching the live site); the nav occupies
  // a SINGLE grid cell spanning cols 12→end on row 3 and lays its items out with
  // flexbox, so the browser sizes each item to its actual text. (An earlier
  // approach placed each item in its own grid column via a label-length
  // heuristic; that both overflowed the 26-col canvas — clipping the trailing
  // "and more" — and was fragile across the differing font metrics of the macOS
  // dev box vs. the Linux build container. Flex sizing is exact and metric-
  // independent.)
  const navItems = nav
    .map((n) => {
      const c = n.slug ? GENRE_COLORS[n.slug] : undefined;
      const style = n.active && c
        ? `background:${c.primary};color:${c.text};`
        : `color:${MUTED_FG};`;
      return `<span class="navitem" style="${style}">${esc(n.label)}</span>`;
    })
    .join("");
  const navHtml = `<div class="cell nav" style="grid-row:3;grid-column:12/-1;">${navItems}</div>`;

  const rows: string[] = [];
  let gridRow = 5; // rows 1-3 = header (3-row wordmark + nav), row 4 = spacer

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
* { margin:0; padding:0; box-sizing:border-box; }
html,body { width:1200px; height:630px; }
body {
  background:${BG}; color:${FG}; overflow:hidden;
  font-family:"Helvetica Neue", Helvetica, Arial, sans-serif;
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
/* Genre nav: one grid cell (cols 10→end) flexing its items left→right so the
   browser sizes each to its text — no fixed columns, no overflow math. */
.nav { overflow:hidden; padding:0; gap:0; align-items:stretch; }
.navitem {
  display:flex; align-items:flex-end; white-space:nowrap;
  padding:0 8px 2px 8px; line-height:1;
}
.wordmark {
  grid-row:1 / span 3; grid-column:1 / span 11;
  font-size:${Math.round(cell * 2.6)}px; font-weight:600; color:${FG};
  align-items:center; overflow:visible;
}
.day { font-weight:500; }
</style></head>
<body>
<div class="cell wordmark">Cartelita</div>
${navHtml}
${rows.join("\n")}
</body></html>`;
}
