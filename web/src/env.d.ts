/// <reference types="astro/client" />

interface Window {
  /** Re-run the grid backstop and announce `gridsync` (Layout.astro), so
      dependents re-place against a tree that was just revealed. */
  syncGrid?: () => void
  /** Re-run the time-aware agenda pass (row packing, now-dots/lines;
      Layout.astro) — for every day, or just `section`. */
  syncAgenda?: (section?: HTMLElement) => void
}
