// The one layout breakpoint. Below 760px the page switches to the narrow
// layout: full-bleed fluid cells, two grid rows per event (time · title, then
// place · price), the stacked navbar and the tap-to-expand event panel. CSS
// can't import this, so every `@media (max-width: 759.98px)` in global.css
// mirrors it; keep the two in sync.
export const NARROW_QUERY = "(max-width: 759.98px)";
