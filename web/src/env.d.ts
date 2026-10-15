/// <reference types="astro/client" />

interface Window {
  /** Re-run the grid backstop and announce `gridsync` (Layout.astro), so
      dependents re-place against a tree that was just revealed. */
  syncGrid?: () => void
  /** Re-run the time-aware agenda pass (row packing, now-dots/lines;
      Layout.astro) — for every day, or just `section`. */
  syncAgenda?: (section?: HTMLElement) => void
  /** Re-pack every GridCheckButtons group for the options it now shows
      (ui/GridCheckButtons.astro). */
  layoutGridChecks?: () => void
  /** Umami's tracker (Layout.astro loads it deferred; absent when blocked).
      Only called through lib/track.ts. */
  umami?: {
    track(name: string, data?: Record<string, string | number | boolean>): Promise<unknown>
  }
}
