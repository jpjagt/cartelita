import type { MapPalette, StyleDoc, StyleLayer } from "@/types/today";

// The Today map's basemap (OpenFreeMap's Positron vector style), repainted
// in the site's own greys: every colour is a mix of the page background
// toward the foreground (palette.ink(t)), so the same rule draws the light
// map on white and the dark map on near-black — no blue water, no coloured
// shields, nothing that competes with the genre-coloured markers. Pure, so
// it's tested apart from MapLibre (lib/today-map.ts).

/** The no-key OpenFreeMap style the map starts from. */
export const BASEMAP_STYLE_URL = "https://tiles.openfreemap.org/styles/positron";

/** How much ink (0 = page background, 1 = foreground) each kind of feature
    gets. Water and buildings sit a little off the land, roads a little more,
    labels at the muted-foreground tone. */
const INK = {
  land: 0,
  residential: 0.015,
  green: 0.035,
  building: 0.05,
  buildingOutline: 0.09,
  water: 0.085,
  waterway: 0.1,
  roadMinor: 0.09,
  roadInner: 0.025,
  roadCasing: 0.15,
  roadSubtle: 0.07,
  rail: 0.13,
  aeroway: 0.03,
  boundary: 0.28,
  labelMinor: 0.5,
  label: 0.62,
  labelMajor: 0.82,
} as const;

/** Layers dropped outright: highway shields (sprite icons in colour) and
    the shaded-relief raster. */
function dropped(layer: StyleLayer): boolean {
  return layer.type === "raster" || /shield/.test(layer.id) || layer.type === "hillshade";
}

/** The ink amount for a fill / line layer, by what it draws. */
function shapeInk(layer: StyleLayer): number {
  const id = layer.id;
  const src = layer["source-layer"] ?? "";
  if (layer.type === "background") return INK.land;
  if (src === "water" || id.startsWith("water")) return layer.type === "line" ? INK.waterway : INK.water;
  if (src === "waterway") return INK.waterway;
  if (src === "building") return INK.building;
  if (src === "park" || /wood|grass|park|landcover/.test(id)) return INK.green;
  if (/ice|glacier/.test(id)) return INK.land;
  if (src === "landuse") return INK.residential;
  if (src === "aeroway") return INK.aeroway;
  if (src === "boundary") return INK.boundary;
  if (/dashline/.test(id)) return INK.land;
  if (/rail/.test(id)) return INK.rail;
  if (/casing/.test(id)) return INK.roadCasing;
  if (/subtle/.test(id)) return INK.roadSubtle;
  if (/inner|pier/.test(id)) return INK.roadInner;
  return INK.roadMinor;
}

/** The ink amount for a symbol layer's text. */
function labelInk(layer: StyleLayer): number {
  const id = layer.id;
  if (/city|country|capital/.test(id)) return INK.labelMajor;
  if (/water|path|waterway/.test(id)) return INK.labelMinor;
  return INK.label;
}

const COLOR_KEYS: Record<string, string[]> = {
  background: ["background-color"],
  fill: ["fill-color", "fill-outline-color"],
  line: ["line-color"],
};

/** A copy of `style` repainted with `palette`. */
export function recolorStyle(style: StyleDoc, palette: MapPalette): StyleDoc {
  const layers = style.layers.filter((l) => !dropped(l)).map((layer) => {
    const paint: Record<string, unknown> = { ...(layer.paint ?? {}) };
    if (layer.type === "symbol") {
      paint["text-color"] = palette.ink(labelInk(layer));
      paint["text-halo-color"] = palette.ink(0, 0.85);
      paint["text-halo-width"] = 1.2;
      // Sprite icons (POIs) would bring colour back.
      paint["icon-opacity"] = 0;
    } else {
      const t = shapeInk(layer);
      for (const key of COLOR_KEYS[layer.type] ?? []) {
        if (key === "fill-outline-color") {
          if (key in paint) paint[key] = palette.ink(layer["source-layer"] === "building" ? INK.buildingOutline : t);
        } else {
          paint[key] = palette.ink(t);
        }
      }
    }
    return { ...layer, paint };
  });
  return { ...style, layers };
}

/** Mix two sRGB colours [r, g, b] (0–255): `t` of the way from `a` to `b`. */
export function mixRgb(a: number[], b: number[], t: number): number[] {
  return a.map((x, i) => Math.round(x + (b[i] - x) * t));
}

/** A palette mixing `background` toward `foreground` (both [r, g, b]). */
export function inkPalette(background: number[], foreground: number[]): MapPalette {
  return {
    ink(t, alpha = 1) {
      const [r, g, b] = mixRgb(background, foreground, t);
      return alpha >= 1 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${alpha})`;
    },
  };
}
