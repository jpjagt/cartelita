/// <reference types="astro/client" />

interface Window {
  /** Recompute grid cell sizing for every .gridpaper (Layout.astro). Exposed so
      the film view toggle can re-sync a tree that was display:none at paint. */
  syncGrid?: () => void
  /** Re-run the time-aware agenda pass (row packing, now-dots/lines;
      Layout.astro) — for every day, or just `section`. */
  syncAgenda?: (section?: HTMLElement) => void
}
