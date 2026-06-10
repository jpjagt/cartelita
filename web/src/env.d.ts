/// <reference types="astro/client" />

interface Window {
  /** Recompute grid cell sizing for every .gridpaper (Layout.astro). Exposed so
      the film view toggle can re-sync a tree that was display:none at paint. */
  syncGrid?: () => void
  /** Re-place the time-aware now-dots/lines (Layout.astro). */
  syncAgenda?: () => void
}
