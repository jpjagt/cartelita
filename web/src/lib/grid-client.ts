import { NARROW_QUERY } from "@/lib/breakpoints";
import { gridGeometry } from "@/lib/grid-geometry";
import type { CssDecls, GridGeometry } from "@/lib/types";

// Browser-side helpers for the scripts that place things on the grid. The
// geometry itself comes from CSS (the build-time step table); these read it
// the same way it was computed, so scripts agree with the CSS by construction.

const NARROW = typeof window !== "undefined" ? window.matchMedia(NARROW_QUERY) : null;

export const isNarrow = (): boolean => NARROW?.matches ?? false;

/** Container-query support: without it the step tables don't apply and
    syncGrid writes the geometry inline instead. */
export const SUPPORTS_CQ =
  typeof CSS !== "undefined" && CSS.supports("container-type", "inline-size");

/** The query container's width — <body>'s content box, what `100cqw` and
    `@container (min-width: …)` measure. Every .gridpaper is full-bleed, so
    it's also each grid's width (including hidden ones). */
export function containerWidth(): number {
  return parseFloat(getComputedStyle(document.body).width) || document.documentElement.clientWidth;
}

/** The grid geometry at the current width — identical to what the CSS step
    table set (--cell may be `calc(100cqw / N)` there, which a script can't
    read back as a number). */
export function liveGrid(): GridGeometry {
  return gridGeometry(containerWidth(), isNarrow());
}

/** Write `desired` custom properties onto `el` inline ONLY where they differ
    from what the stylesheets (the build-time step tables) already resolve to,
    and drop stale inline overrides. The common case — the build-time values
    are right — writes nothing, so nothing re-lays out. */
export function correctVars(el: HTMLElement, desired: CssDecls): void {
  for (const k of Object.keys(desired)) el.style.removeProperty(k);
  const cs = getComputedStyle(el);
  for (const [k, v] of Object.entries(desired)) {
    if (cs.getPropertyValue(k).trim() !== v) el.style.setProperty(k, v);
  }
}

let ctx: CanvasRenderingContext2D | null | undefined;

/** `el`'s text advance at font-size 1px, measured in the font the browser is
    actually rendering it in (for labels the bundled font can't cover). */
export function measureEm(el: HTMLElement): number {
  ctx ??= document.createElement("canvas").getContext("2d");
  const cs = getComputedStyle(el);
  const size = parseFloat(cs.fontSize) || 16;
  if (!ctx) return 0;
  ctx.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
  return ctx.measureText(el.textContent?.trim() ?? "").width / size;
}
