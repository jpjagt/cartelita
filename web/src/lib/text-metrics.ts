import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { create, type Font } from "fontkit";
import { FALLBACK_ADVANCES } from "@/lib/fallback-advances";
import type { TextMeasure } from "@/lib/types";

// BUILD-TIME text measurement (Astro frontmatter, never shipped to the
// browser). Labels whose width decides how many whole cells they span — navbar
// links, GridRadioButtons labels, prices — are measured here with the font the
// page actually renders, so the server-rendered spans are already right and
// the first paint doesn't reflow when the client scripts run.
//
// The font: the CSS stack is "Helvetica Neue", Helvetica, "TeX Gyre Heros",
// Arial. TeX Gyre Heros (bundled in public/fonts) is a metric-compatible
// Helvetica clone, so its advances match Helvetica Neue on Apple devices and
// are exactly what everyone else renders once the webfont loads. (Before it
// loads, font-display: swap shows Arial — the text may differ by a pixel or
// two, but the cell spans are fixed by the SSR, so nothing moves.)
//
// Scripts the font lacks (Cyrillic for ru, Armenian for hy) render in a
// device fallback font we can't know at build time. For those characters we
// ESTIMATE an advance — per letter, as Apple's fallbacks render it
// (Helvetica Neue's Cyrillic, macOS's Armenian font; lib/fallback-advances.ts),
// so Apple visitors usually need no correction — and mark the label
// `covered: false`. The client measurers re-measure exactly those labels in the
// browser and correct them (Navbar.astro, GridRadioButtons.astro,
// EventRow.astro). Latin pages never run them.

/** Fallback-font advances (em) by letter, from lib/fallback-advances.ts. */
const FALLBACK = new Map<string, number>(
  Object.values(FALLBACK_ADVANCES).flatMap((table) =>
    table.split(" ").map((cell): [string, number] => {
      const [ch] = [...cell];
      return [ch, Number(cell.slice(ch.length)) / 1000];
    }),
  ),
);

const FONT_FILE = "public/fonts/TeXGyreHeros-Regular.woff2";

let font: Font | null = null;
let meanLower = 0;
let meanUpper = 0;

function loadFont(): Font {
  if (font) return font;
  // Astro (build), vitest and vite-node all run from the web/ root; the
  // compiled frontmatter lives elsewhere, so don't resolve from import.meta.
  const candidates = [join(process.cwd(), FONT_FILE), join(process.cwd(), "web", FONT_FILE)];
  const path = candidates.find((p) => existsSync(p));
  if (!path) throw new Error(`text-metrics: font not found (tried ${candidates.join(", ")})`);
  const f = create(readFileSync(path)) as Font;
  const mean = (chars: string) =>
    [...chars].reduce((a, c) => a + f.glyphForCodePoint(c.codePointAt(0)!).advanceWidth, 0) /
    chars.length /
    f.unitsPerEm;
  meanLower = mean("abcdefghijklmnopqrstuvwxyz");
  meanUpper = mean("ABCDEFGHIJKLMNOPQRSTUVWXYZ");
  font = f;
  return f;
}

/** Estimated advance (em) of one character the font lacks: its fallback
    advance when known, else the font's mean Latin letter of the same case. */
function estimate(c: string): number {
  const known = FALLBACK.get(c);
  if (known !== undefined) return known;
  const upper = c.toUpperCase() === c && c.toLowerCase() !== c;
  return upper ? meanUpper : meanLower;
}

const cache = new Map<string, TextMeasure>();

/** Advance width of `text` at font-size 1px (multiply by the px size), with
    the font's kerning applied, as a browser lays it out on one line. Runs of
    characters the font lacks are estimated (see above). */
export function measureText(text: string): TextMeasure {
  const hit = cache.get(text);
  if (hit) return hit;
  const f = loadFont();
  let em = 0;
  let covered = true;
  let run = "";
  const flush = () => {
    if (!run) return;
    const laid = f.layout(run);
    em += laid.positions.reduce((a, p) => a + p.xAdvance, 0) / f.unitsPerEm;
    run = "";
  };
  for (const c of text) {
    if (f.hasGlyphForCodePoint(c.codePointAt(0)!)) {
      run += c;
    } else {
      flush();
      covered = false;
      em += estimate(c);
    }
  }
  flush();
  const m = { em, covered };
  cache.set(text, m);
  return m;
}
