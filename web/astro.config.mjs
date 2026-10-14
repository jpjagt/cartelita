import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  site: "https://cartelita.july.dev",
  output: "static",
  // Client navigation (ClientRouter, Layout.astro): page links prefetch on
  // hover/focus. Not "viewport"/"load": a page is up to ~1.8 MB of HTML, too
  // much to fetch speculatively for every tab on a phone. Not "tap" either: on
  // touch the click follows touchstart too closely, so the prefetch and the
  // navigation's own fetch both download the page.
  prefetch: { prefetchAll: true, defaultStrategy: "hover" },
  vite: {
    plugins: [tailwindcss()],
  },
});
