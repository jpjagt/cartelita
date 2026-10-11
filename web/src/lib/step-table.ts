import { NARROW_QUERY } from "@/lib/breakpoints";
import { GRID_TABLE } from "@/lib/grid-geometry";
import type { CssDecls, StepFn, StepTable } from "@/lib/types";

// Container-query step tables. Anything the page lays out as a function of the
// container (body) width — the grid geometry, navbar link placement, radio
// label spans, price widths — is a step function of it: constant over ranges,
// changing at a few widths. Sweeping `fn` over the covered widths at build
// time and emitting one `@container (min-width: …)` rule per change point lets
// the CSS reproduce the JS result at every width on the very first paint, with
// no script and no typed CSS arithmetic (not yet in Safari 18 / Firefox ESR).
//
// Rules are emitted in ascending min-width order and each carries only the
// declarations that changed: every rule at or below the container width
// matches, and later ones win, so the cumulative result is fn(width).

/** Thresholds are located to 1/4096 px by bisection, then written to 1/100 px
    for the rule: the lowest such width already showing the new value, which
    leaves at most a 0.01px window in which the CSS still shows the old one. */
const BISECT_STEPS = 12;

const same = (a: CssDecls, b: CssDecls) => {
  const ka = Object.keys(a);
  return ka.length === Object.keys(b).length && ka.every((k) => a[k] === b[k]);
};

function diff(prev: CssDecls, next: CssDecls): CssDecls {
  const out: CssDecls = {};
  for (const [k, v] of Object.entries(next)) if (prev[k] !== v) out[k] = v;
  return out;
}

/** Steps of `fn` over [min, max) in one mode: the value at `min`, then each
    (rounded-up) width at which it changes with the declarations that changed. */
function sweep(fn: StepFn, narrow: boolean, min: number, max: number) {
  const base = fn(min, narrow);
  const steps: { minWidth: number; decls: CssDecls }[] = [];
  let cur = base;
  for (let w = min + 1; w < max; w++) {
    const next = fn(w, narrow);
    if (same(cur, next)) continue;
    // One or more changes inside (w-1, w]: walk them in order.
    let lo = w - 1;
    while (!same(cur, next)) {
      let a = lo;
      let b = w;
      for (let i = 0; i < BISECT_STEPS; i++) {
        const mid = (a + b) / 2;
        if (same(fn(mid, narrow), cur)) a = mid;
        else b = mid;
      }
      const value = fn(b, narrow);
      const down = Math.floor(b * 100) / 100;
      const at = down > a && same(fn(down, narrow), value) ? down : Math.min(w, Math.ceil(b * 100) / 100);
      steps.push({ minWidth: at, decls: diff(cur, value) });
      cur = value;
      lo = b;
    }
  }
  return { base, steps };
}

/** Sweep `fn` over the covered container widths of both layout modes. */
export function stepTable(fn: StepFn, range = GRID_TABLE): StepTable {
  return {
    narrow: sweep(fn, true, range.narrow.min, range.narrow.max),
    wide: sweep(fn, false, range.wide.min, range.wide.max),
  };
}

const decl = (d: CssDecls) =>
  Object.entries(d)
    .map(([k, v]) => `${k}:${v}`)
    .join(";");

const fmt = (px: number) => `${+px.toFixed(2)}px`;

/** Render a step table as CSS for `selector`. The base values apply with no
    container condition (so they're also the fallback where container queries
    are unsupported); each step is an @container rule against the nearest
    query container — <body>, `container-type: inline-size` in global.css. */
export function renderStepCss(selector: string, table: StepTable): string {
  const block = (t: StepTable["narrow"]) => {
    const lines: string[] = [];
    if (Object.keys(t.base).length) lines.push(`${selector}{${decl(t.base)}}`);
    for (const s of t.steps) {
      if (!Object.keys(s.decls).length) continue;
      lines.push(`@container (min-width:${fmt(s.minWidth)}){${selector}{${decl(s.decls)}}}`);
    }
    return lines.join("\n");
  };
  const wide = block(table.wide);
  const narrow = block(table.narrow);
  return [
    wide && `@media not all and ${NARROW_QUERY}{\n${wide}\n}`,
    narrow && `@media ${NARROW_QUERY}{\n${narrow}\n}`,
  ]
    .filter(Boolean)
    .join("\n");
}
