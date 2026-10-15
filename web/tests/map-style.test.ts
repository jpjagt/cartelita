import { describe, it, expect } from "vitest";
import { inkPalette, mixRgb, recolorStyle } from "@/lib/map-style";
import type { StyleDoc } from "@/types/today";

const style: StyleDoc = {
  version: 8,
  layers: [
    { id: "background", type: "background", paint: { "background-color": "rgb(242,243,240)" } },
    { id: "ne2_shaded", type: "raster", source: "ne2_shaded" },
    { id: "water", type: "fill", "source-layer": "water", paint: { "fill-color": "rgb(194, 200, 202)" } },
    {
      id: "building",
      type: "fill",
      "source-layer": "building",
      paint: { "fill-color": "#eee", "fill-outline-color": "#ddd" },
    },
    { id: "highway_major_casing", type: "line", "source-layer": "transportation", paint: { "line-color": "#d5d5d5" } },
    { id: "highway_major_inner", type: "line", "source-layer": "transportation", paint: { "line-color": "#fff" } },
    { id: "highway-shield-non-us", type: "symbol", "source-layer": "transportation_name" },
    {
      id: "water_name_point_label",
      type: "symbol",
      "source-layer": "water_name",
      paint: { "text-color": "#495e91" },
      layout: { "text-font": ["Noto Sans Italic"] },
    },
    { id: "label_city", type: "symbol", "source-layer": "place", paint: { "text-color": "#000" } },
  ],
};

const white = [255, 255, 255];
const black = [0, 0, 0];

describe("map style recolour", () => {
  const out = recolorStyle(style, inkPalette(white, black));
  const layer = (id: string) => out.layers.find((l) => l.id === id);

  it("drops shields and the shaded-relief raster", () => {
    expect(layer("ne2_shaded")).toBeUndefined();
    expect(layer("highway-shield-non-us")).toBeUndefined();
  });

  it("paints the land in the page background", () => {
    expect(layer("background")?.paint?.["background-color"]).toBe("rgb(255, 255, 255)");
  });

  it("leaves no colour behind: every paint colour is a grey", () => {
    for (const l of out.layers) {
      for (const [key, value] of Object.entries(l.paint ?? {})) {
        if (!key.endsWith("color")) continue;
        const m = String(value).match(/rgba?\((\d+), (\d+), (\d+)/);
        expect(m, `${l.id} ${key}`).not.toBeNull();
        expect(new Set(m!.slice(1)).size, `${l.id} ${key}`).toBe(1);
      }
    }
  });

  it("keeps casings darker than road fills and water off the land", () => {
    const grey = (id: string, key: string) => Number(String(layer(id)?.paint?.[key]).match(/\d+/)![0]);
    expect(grey("highway_major_casing", "line-color")).toBeLessThan(grey("highway_major_inner", "line-color"));
    expect(grey("water", "fill-color")).toBeLessThan(255);
    expect(grey("label_city", "text-color")).toBeLessThan(grey("water_name_point_label", "text-color"));
  });

  it("inverts with the theme: dark land, light labels", () => {
    const dark = recolorStyle(style, inkPalette([10, 10, 10], [250, 250, 250]));
    expect(dark.layers[0].paint?.["background-color"]).toBe("rgb(10, 10, 10)");
    const city = dark.layers.find((l) => l.id === "label_city");
    expect(Number(String(city?.paint?.["text-color"]).match(/\d+/)![0])).toBeGreaterThan(150);
  });

  it("does not mutate the source style", () => {
    expect(style.layers[0].paint?.["background-color"]).toBe("rgb(242,243,240)");
  });

  it("mixes colours linearly", () => {
    expect(mixRgb([0, 100, 200], [100, 100, 0], 0.5)).toEqual([50, 100, 100]);
    expect(inkPalette(white, black).ink(0, 0.5)).toBe("rgba(255, 255, 255, 0.5)");
  });
});
