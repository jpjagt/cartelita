import type {
  CssDecls,
  GridGeometry,
  NavFit,
  NavFlow,
  NavLayout,
  NavLine,
  NavMenuPlacement,
  NavModel,
  NavPlacement,
  NavSpans,
} from "@/lib/types";
import { cellSpan, LABEL_CELLS } from "@/lib/price-fit";

// The navbar's layout (Navbar.astro), pure so it can be swept into a
// build-time step table and tested for overlaps. Everything places onto the
// one page grid by column line, spanning the whole cells its label needs:
//
//   desktop  [Cartelita  ]                         [Amsterdam ▾] · [NL][EN]
//            [ 11 × 3    ]
//            [           ][Jazz][Classical][More ▾] · · · [Film][My list]
//
//   narrow   [Cartelita][Amsterdam ▾]      (wordmark 9 × 2; city, locales
//            [         ][NL][EN]            right-flush beside it)
//            [Jazz][Classical][More ▾] · · [Film][My list]   (rows 3–4)
//
// Genre tabs come in volume order (lib/genre-nav.ts). Genres below the weekly
// threshold — and any tail that doesn't fit the tab row(s) at this width — sit
// in the More dropdown, so the bar never wraps into many rows. Film and My
// list are set apart, right-aligned on the last tab row after at least
// NAV_GAP empty cells.

/** Desktop wordmark width in cells (.navbar-wordmark, rows 1–3). */
export const WORDMARK_COLS = 11;
/** Narrow wordmark width in cells (.navbar-wordmark, rows 1–2). */
export const NARROW_WORDMARK_COLS = 9;
/** Empty cells between the genre tabs and the set-apart Film · My list, and
    between the city selector and the locale switcher. */
export const NAV_GAP = 1;
/** Narrow: at most this many tab rows below the wordmark. */
export const NARROW_TAB_ROWS = 2;
/** Desktop: the tabs stay on row 3 beside the wordmark while that shows at
    least this many genre tabs (or as many as there are, or as many as the
    full-width row 4 below it would); otherwise they move below it. */
export const MIN_BESIDE_TABS = 3;
/** Smallest city trigger: one cell of (truncated) name + the chevron. */
const MIN_CITY_SPAN = 2;

export function navSpans(m: NavModel, g: GridGeometry): NavSpans {
  const span = (em: number) => cellSpan(em * g.fontSize, g.cell, LABEL_CELLS);
  const genres = m.genres.map(span);
  return {
    genres,
    tabbable: m.tabbable,
    active: m.active,
    more: span(m.more) + 1,
    activeMore: m.active >= 0 ? genres[m.active] + 1 : 0,
    fixed: m.fixed.map(span),
    city: span(m.city) + 1,
    cityMenu: m.cityMenu.map(span),
    localeCount: m.localeCount,
  };
}

const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);

/** Flow `items` left to right along `lines`, moving to the next line when one
    doesn't fit, and right-align `fixed` on the LAST line, at least NAV_GAP
    cells after the flow. Null when they don't all fit. */
export function flowLines(items: number[], fixed: number[], lines: NavLine[]): NavFlow | null {
  const last = lines.length - 1;
  const fixedTotal = sum(fixed);
  const endOf = (i: number) =>
    i === last && fixedTotal > 0 ? lines[i].end - fixedTotal - NAV_GAP : lines[i].end;
  const flow: NavPlacement[] = [];
  let li = 0;
  let col = lines[0].start;
  for (const span of items) {
    while (li <= last && col + span > endOf(li)) {
      li += 1;
      if (li <= last) col = lines[li].start;
    }
    if (li > last) return null;
    flow.push({ col, span, row: lines[li].row });
    col += span;
  }
  const line = lines[last];
  if (fixedTotal > line.end - line.start) return null;
  let fc = line.end - fixedTotal;
  return {
    flow,
    fixed: fixed.map((span) => {
      const p = { col: fc, span, row: line.row };
      fc += span;
      return p;
    }),
  };
}

/** Most genre tabs the tab could take (the threshold run, see tabbableCount). */
const maxTabs = (sp: NavSpans) => Math.min(sp.genres.length, sp.tabbable);

/** The most genre tabs (in order, up to the tabbable run) that fit on
    `lines` together with the More trigger for the rest and the set-apart
    tabs. A More holding a single genre is pointless: when that genre's own
    tab fits instead, it gets one. Null when not even More fits. */
export function fitTabs(sp: NavSpans, lines: NavLine[]): NavFit | null {
  const n = sp.genres.length;
  const attempt = (k: number): NavFit | null => {
    const items = sp.genres.slice(0, k);
    if (k < n) items.push(sp.active >= k ? sp.activeMore : sp.more);
    const r = flowLines(items, sp.fixed, lines);
    return r && { k, ...r };
  };
  for (let k = maxTabs(sp); k >= 0; k--) {
    const all = n - k === 1 ? attempt(n) : null;
    if (all) return all;
    const r = attempt(k);
    if (r) return r;
  }
  return null;
}

/** Last resort for widths too small for even More + the set-apart tabs:
    everything flows down from `row`, each item clamped to the band. */
function forced(sp: NavSpans, start: number, end: number, row: number): NavFit {
  const n = sp.genres.length;
  const items = [...(n ? [sp.active >= 0 ? sp.activeMore : sp.more] : []), ...sp.fixed];
  let col = start;
  const placed = items.map((s) => {
    const span = Math.max(1, Math.min(s, end - start));
    if (col + span > end && col > start) {
      row += 1;
      col = start;
    }
    const p = { col, span, row };
    col += span;
    return p;
  });
  return { k: 0, flow: placed.slice(0, n ? 1 : 0), fixed: placed.slice(n ? 1 : 0) };
}

/** Pick the tab rows and how many tabs they show. Desktop: row 3 beside the
    wordmark, or the full-width row 4 below it when beside is too cramped
    (MIN_BESIDE_TABS). Narrow: the fewest of rows 3, 4, … (NARROW_TAB_ROWS)
    that show the most tabs. */
function chooseTabs(sp: NavSpans, start: number, end: number, narrow: boolean): NavFit {
  if (narrow) {
    let best: NavFit | null = null;
    for (let rows = 1; rows <= NARROW_TAB_ROWS; rows++) {
      const lines = Array.from({ length: rows }, (_, i) => ({ row: 3 + i, start, end }));
      const r = fitTabs(sp, lines);
      if (r && (!best || r.k > best.k)) best = r;
    }
    return best ?? forced(sp, start, end, 3);
  }
  const beside = fitTabs(sp, [{ row: 3, start: start + WORDMARK_COLS, end }]);
  const below = fitTabs(sp, [{ row: 4, start, end }]);
  if (beside && (!below || beside.k >= below.k || beside.k >= Math.min(MIN_BESIDE_TABS, maxTabs(sp)))) {
    return beside;
  }
  return below ?? forced(sp, start, end, 4);
}

/** The navbar on a band of `bandCells` columns (column lines from 1). */
export function layoutNav(sp: NavSpans, bandCells: number, narrow: boolean): NavLayout {
  const start = 1;
  const end = start + bandCells;
  const count = sp.localeCount;

  // Top-right zone: city selector, gap, locales.
  let city: NavPlacement;
  const locales: NavPlacement[] = [];
  const rightFlush = (row: number) => {
    for (let i = 0; i < count; i++) locales.push({ col: end - count + i, span: 1, row });
  };
  if (!narrow) {
    const room = end - count - NAV_GAP - (start + WORDMARK_COLS + NAV_GAP);
    const span = Math.max(MIN_CITY_SPAN, Math.min(sp.city, room));
    city = { col: end - count - NAV_GAP - span, span, row: 1 };
    rightFlush(1);
  } else {
    const room = bandCells - NARROW_WORDMARK_COLS;
    if (sp.city + NAV_GAP + count <= room) {
      city = { col: end - count - NAV_GAP - sp.city, span: sp.city, row: 1 };
      rightFlush(1);
    } else {
      const span = Math.max(MIN_CITY_SPAN, Math.min(sp.city, room));
      city = { col: end - span, span, row: 1 };
      rightFlush(2);
    }
  }
  const cityWidth = Math.min(bandCells, Math.max(Math.max(0, ...sp.cityMenu) + 1, city.span));
  // Under the trigger, shifted left as far as it must to stay in the band.
  const cityMenu: NavMenuPlacement = {
    col: Math.max(start, Math.min(city.col, end - cityWidth)),
    row: city.row,
    width: cityWidth,
  };

  // Tabs.
  const fit = chooseTabs(sp, start, end, narrow);
  const n = sp.genres.length;
  const tabs = sp.genres.map((_, i) => (i < fit.k ? fit.flow[i] : null));
  const more = fit.k < n ? fit.flow[fit.k] : null;
  let moreMenu: NavMenuPlacement | null = null;
  if (more) {
    const width = Math.min(
      bandCells,
      Math.max(Math.max(...sp.genres.slice(fit.k)) + 1, more.span),
    );
    moreMenu = { col: Math.max(start, Math.min(more.col, end - width)), row: more.row, width };
  }
  return {
    tabs,
    more,
    moreMenu,
    moreShowsActive: !!more && sp.active >= fit.k,
    fixed: fit.fixed,
    city,
    cityMenu,
    locales,
  };
}

/** The navbar's placement as CSS custom properties on the header, for model
    `m` on a grid of `g`'s geometry. Columns are offsets from --col-start.
    Genre i: tab --t{i}c/s/r, shown when --t{i}d is `flex`; its More entry
    shown when --m{i}d is `flex`, on menu row --m{i}r. The More trigger sits
    at --mtc/s/r, plain when --mtd is `flex`, showing the active genre when
    --mad is; its menu at --mmc/--mmr, --mmw × --mmh cells. Set-apart tab j:
    --f{j}c/s/r. City: --cc/s/r, its menu --cmc/--cmr/--cmw. Locale i:
    --l{i}c/r. Shared by the build-time step table (Navbar.astro) and the
    client correction, so both produce identical values. */
export function navVars(m: NavModel, g: GridGeometry, narrow: boolean): CssDecls {
  const nav = layoutNav(navSpans(m, g), g.bandCells, narrow);
  const off = (col: number) => String(col - 1);
  const out: CssDecls = {};
  const place = (prefix: string, p: NavPlacement | null) => {
    out[`${prefix}c`] = p ? off(p.col) : "0";
    out[`${prefix}s`] = p ? String(p.span) : "1";
    out[`${prefix}r`] = p ? String(p.row) : "1";
  };
  const k = nav.tabs.filter(Boolean).length;
  nav.tabs.forEach((p, i) => {
    place(`--t${i}`, p);
    out[`--t${i}d`] = p ? "flex" : "none";
    out[`--m${i}d`] = p ? "none" : "flex";
    out[`--m${i}r`] = p ? "1" : String(i - k + 1);
  });
  place("--mt", nav.more);
  out["--mtd"] = nav.more && !nav.moreShowsActive ? "flex" : "none";
  out["--mad"] = nav.more && nav.moreShowsActive ? "flex" : "none";
  out["--mmc"] = nav.moreMenu ? off(nav.moreMenu.col) : "0";
  out["--mmr"] = String(nav.moreMenu?.row ?? 1);
  out["--mmw"] = String(nav.moreMenu?.width ?? 1);
  out["--mmh"] = String(nav.tabs.length - k || 1);
  nav.fixed.forEach((p, j) => place(`--f${j}`, p));
  place("--c", nav.city);
  out["--cmc"] = off(nav.cityMenu.col);
  out["--cmr"] = String(nav.cityMenu.row);
  out["--cmw"] = String(nav.cityMenu.width);
  nav.locales.forEach((p, i) => {
    out[`--l${i}c`] = off(p.col);
    out[`--l${i}r`] = String(p.row);
  });
  return out;
}
