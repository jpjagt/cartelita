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

import type { AgendaDay } from "@/lib/types";
import { localeTag } from "@/i18n";

interface RenderOgArgs {
  locale: Locale;
  list: string;
  lists: string[];
  days: AgendaDay[];
}

// Dark palette values mirrored from .dark in global.css (resolved to hex-ish
// strings Playwright/Chromium renders identically; oklch is fine here too).
const BG = "oklch(0.145 0 0)";
const FG = "oklch(0.985 0 0)";
const MUTED_FG = "oklch(0.708 0 0)";
const MUTED_BG = "oklch(0.269 0 0)";
const GRID_LINE = MUTED_BG;

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

  // Header: wordmark on the left, genre nav flowing after it on the wordmark's
  // baseline row. The wordmark spans the first ~9 cols / 2 rows; nav sits on row 2.
  const navHtml = nav
    .map((n) => {
      const c = n.slug ? GENRE_COLORS[n.slug] : undefined;
      const style = n.active && c
        ? `background:${c.primary};color:${c.text};`
        : `color:${MUTED_FG};`;
      return `<span class="cell" style="grid-row:2;${style}">${esc(n.label)}</span>`;
    })
    .join("");

  const rows: string[] = [];
  let gridRow = 4; // rows 1-2 = header, row 3 = spacer

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
.wordmark {
  grid-row:1 / span 2; grid-column:1 / span 9;
  font-size:${Math.round(cell * 2.2)}px; font-weight:600; color:${FG};
  align-items:center;
}
.day { font-weight:500; }
</style></head>
<body>
<div class="cell wordmark">Cartelita</div>
${navHtml}
${rows.join("\n")}
</body></html>`;
}
