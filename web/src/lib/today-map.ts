import {
  AttributionControl,
  LngLatBounds,
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  setWorkerUrl,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { BASEMAP_STYLE_URL, inkPalette, recolorStyle } from "@/lib/map-style";
import type { MapVenue, MapVenues, StyleDoc, TodayMapHandle, TodayMapOptions } from "@/types/today";

// The Today page's map (pages/[city]/[locale]/today.astro). This module —
// MapLibre and its stylesheet included — is imported dynamically the first
// time the map view opens, so the list view's bundle never carries it.
//
// The basemap is OpenFreeMap's Positron (no API key), repainted in the
// site's greys from its own colour tokens (lib/map-style.ts) and again on
// every theme switch. Venues are HTML markers styled as grid cells
// (global.css .map-marker): the venue's count of events still to come
// today, filled in its genre colour while selected.

// The bundled worker (Vite emits it as its own file).
setWorkerUrl(new URL(workerUrl, location.href).href);

let baseStyle: Promise<StyleDoc> | null = null;
function loadBaseStyle(): Promise<StyleDoc> {
  baseStyle ??= fetch(BASEMAP_STYLE_URL).then((r) => {
    if (!r.ok) throw new Error(`basemap style: HTTP ${r.status}`);
    return r.json() as Promise<StyleDoc>;
  });
  baseStyle.catch(() => (baseStyle = null)); // retry on the next map
  return baseStyle;
}

let ctx: CanvasRenderingContext2D | null | undefined;

/** A CSS colour token (e.g. --background, an oklch() value) as sRGB, by
    painting it on a 1px canvas. */
function tokenRgb(name: string, fallback: number[]): number[] {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  ctx ??= document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  if (!value || !ctx) return fallback;
  ctx.clearRect(0, 0, 1, 1);
  ctx.fillStyle = "#000";
  ctx.fillStyle = value;
  ctx.fillRect(0, 0, 1, 1);
  const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
  return [r, g, b];
}

/** The basemap in the current theme's colours. */
async function themedStyle(): Promise<StyleDoc> {
  const base = await loadBaseStyle();
  const dark = document.documentElement.classList.contains("dark");
  return recolorStyle(
    base,
    inkPalette(
      tokenRgb("--background", dark ? [10, 10, 10] : [255, 255, 255]),
      tokenRgb("--foreground", dark ? [250, 250, 250] : [10, 10, 10]),
    ),
  );
}

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** The cell size the page grid uses here, in px (map padding, marker size). */
function cellPx(el: HTMLElement): number {
  return parseFloat(getComputedStyle(el).getPropertyValue("--cell")) || el.clientWidth / 20 || 32;
}

export async function createTodayMap(opts: TodayMapOptions): Promise<TodayMapHandle> {
  const { container, onSelect } = opts;
  const style = await themedStyle();
  const map = new MapLibreMap({
    container,
    // MapLibre's style type is far stricter than this loose document.
    style: style as never,
    center: opts.center,
    zoom: 12,
    attributionControl: false,
    dragRotate: false,
    pitchWithRotate: false,
    touchPitch: false,
    renderWorldCopies: false,
    fadeDuration: 0,
  });
  map.touchZoomRotate.disableRotation();
  map.keyboard.disableRotation();
  map.addControl(new NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new AttributionControl({ compact: true }), "bottom-right");

  const markers = new Map<string, { marker: Marker; el: HTMLButtonElement }>();
  let selected: string | null = null;
  let fittedKey = "";
  let destroyed = false;

  // A click on the map itself (not a marker) closes the panel.
  map.on("click", () => onSelect(null));

  function markerEl(v: MapVenue): HTMLButtonElement {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "map-marker";
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      onSelect(el.dataset.venue === selected ? null : (el.dataset.venue ?? null));
    });
    el.dataset.venue = v.slug;
    return el;
  }

  function fit(venues: MapVenue[]) {
    const key = venues.map((v) => v.slug).join(" ");
    if (key === fittedKey || !venues.length) return;
    const first = fittedKey === "";
    fittedKey = key;
    const pad = cellPx(container) * 1.5;
    const duration = first || reducedMotion() ? 0 : 400;
    if (venues.length === 1) {
      map.easeTo({ center: [venues[0].lng, venues[0].lat], zoom: 15, duration });
      return;
    }
    const bounds = new LngLatBounds();
    venues.forEach((v) => bounds.extend([v.lng, v.lat]));
    map.fitBounds(bounds, { padding: pad, maxZoom: 15, duration });
  }

  function update(data: MapVenues) {
    if (destroyed) return;
    const keep = new Set(data.venues.map((v) => v.slug));
    for (const [slug, m] of markers) {
      if (!keep.has(slug)) {
        m.marker.remove();
        markers.delete(slug);
      }
    }
    for (const v of data.venues) {
      let m = markers.get(v.slug);
      if (!m) {
        const el = markerEl(v);
        const marker = new Marker({ element: el, anchor: "center" }).setLngLat([v.lng, v.lat]).addTo(map);
        m = { marker, el };
        markers.set(v.slug, m);
      }
      m.el.dataset.genre = v.genre;
      m.el.textContent = String(v.items.length);
      m.el.setAttribute("aria-label", `${v.name}: ${v.items.length}`);
      m.el.toggleAttribute("data-active", v.slug === selected);
    }
    fit(data.venues);
  }

  function select(slug: string | null) {
    selected = slug;
    // (global.css lifts the active marker above its neighbours.)
    for (const [s, m] of markers) m.el.toggleAttribute("data-active", s === slug);
  }

  // Theme switches (Layout.astro toggles .dark on <html>) repaint the basemap.
  let dark = document.documentElement.classList.contains("dark");
  const observer = new MutationObserver(() => {
    const now = document.documentElement.classList.contains("dark");
    if (now === dark) return;
    dark = now;
    themedStyle()
      .then((s) => !destroyed && map.setStyle(s as never, { diff: true }))
      .catch(() => {});
  });
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

  return {
    update,
    select,
    resize: () => !destroyed && map.resize(),
    destroy() {
      destroyed = true;
      observer.disconnect();
      markers.clear();
      map.remove();
    },
  };
}
