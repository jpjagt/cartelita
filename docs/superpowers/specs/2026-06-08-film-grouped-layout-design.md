# Film grouped (masonry) layout — design

Date: 2026-06-08

## Problem

The shared grid layout (`AgendaDay` + `EventRow` on the `.gridpaper` grid) works
well for most categories, where each event is a distinct row of
`time · title · place · price`. For the **film** category it is inefficient:

1. Film titles are short, so the wide title column is mostly empty.
2. The same film screens many times per day, so its title is repeated on every
   row instead of being grouped with its showtimes.

## Goal

For the film category only, group a day's events by film, showing each film title
once with its showtimes listed beneath it, packed into a multi-column masonry of
film cards — while staying on the existing shared cell grid so the paper texture
and grid lines remain aligned.

## Trigger

Hardcoded by genre. The cinema category slug is `"film"` (confirmed in
`queries.ts` `PREFERRED_LIST_ORDER` and `i18n/index.ts`). In
`[locale]/[list].astro`, when `list === "film"`, render a new `<FilmDay>`
component per day instead of `<AgendaDay>`. All other categories keep
`AgendaDay` + `EventRow` untouched.

## Components

New, film-specific components — the shared row components are not modified:

- `FilmDay.astro` — one logical day. Renders the full-band day header (same as
  `AgendaDay`), then the packed grid of film cards, then the spacer row.
- `FilmCard.astro` — one film: a full-card-width semibold title row (plain text),
  followed by one link row per showtime.

Grouping/packing logic lives in a new helper module (`lib/film-agenda.ts`) so the
components stay presentational and the logic is unit-testable.

## Data shape

New helper groups a day's `AgendaEvent[]` into films:

```
FilmGroup {
  title: string                 // resolved per-locale, the group key
  showtimes: AgendaEvent[]      // sorted by existing timeSortKey
  earliestKey: string           // timeSortKey of first showtime (for ordering)
}
```

- Films keyed by resolved `title`.
- Showtimes within a film sorted by the existing `timeSortKey`.
- Films ordered by `earliestKey` (earliest showtime first).
- Each showtime retains its own `startTime`, `venueName`, `price`, `sourceUrl`.

Types go in `src/types/*.ts` per project convention (not inline), except Astro
`Props`.

## Masonry packing (build time)

Astro runs at build, so packing is computed server-side and emitted as explicit
grid coordinates — no runtime JS, no CSS masonry (`grid-template-rows: masonry`
is not reliably supported).

Card height in cells: `1 + N` where N = number of showtimes (1 title row + N
showtime rows).

Packing algorithm (shortest-column, order-preserving):

1. Maintain an array of `K` column heights (cells), all 0. K = column count.
2. Iterate films in `earliestKey` order.
3. Assign the film to the column with the smallest current height (ties → leftmost,
   which keeps left-to-right reading order as much as masonry allows).
4. Record `{ col, rowOffset: thatColumnHeight }`.
5. Increase that column's height by `cardHeight + 1` (1-cell gutter between cards).

This yields balanced columns while preserving earliest-showtime left-to-right
ordering.

### Both breakpoints packed

Column count changes with viewport: 3 (desktop) / 2 (≤768px) / 1 (≤640px).
Per the chosen approach, the build computes **both** the 3-column and 2-column
packings. Each card carries both results as CSS custom properties
(`--col3`/`--row3` and `--col2`/`--row2`); media queries select which apply. The
1-column case uses natural flow (single column, cards stacked).

## Grid placement

Band is `--band-cells: 40`, left edge `--col-start`.

- **Desktop (3 col):** 3 columns × 12 cells + 2 gutters × 2 cells = 40.
  Card column band = 12 cells.
- **≤768px (2 col):** 2 columns × 19 cells + 1 gutter × 2 cells = 40.
  Card column band = 19 cells.
- **≤640px (1 col):** single column spanning the band; reuse the existing
  two-rows-per-event mobile split for showtime rows.

Cards emit explicit `grid-column` (from the packed col index × band stride) and
`grid-row` (header is row 1; `2 + rowOffset`), so they sit on the shared
`.gridpaper` cells and the texture/lines align by construction — same model as
the existing layout. New `.gc-film-*` CSS classes parallel the existing `.gc-*`
placement classes.

## Card internals

- **Title:** semibold, spans the full card-band width, on its own row, plain text
  (not a link). `.cell` + `.cell-truncate`.
- **Showtime rows:** each row is an `<a href={showtime.sourceUrl}>` (own tab,
  `rel="noopener"`), laid out within the card band as
  `time(2) · place(grows, left) · price(3)`. Reuse `.cell`, `.cell-truncate`,
  `.cell-genre-hover` hover styling.
  - Desktop/md: place grows in the middle (band − 2 − 3 cells).
  - Mobile (≤640px): reuse the two-row split (time+place row, price row) as in
    the existing `@media (max-width: 640px)` block.

## Visibility script

The existing day/row show-hide script (Layout.astro) keys off `data-date`
(on the day `<section>`) and `data-time` (on each event wrapper). `FilmDay`
carries `data-date`; each showtime row/link carries `data-time` so the 05:00
boundary correction continues to hide past showtimes correctly. Cards with all
showtimes hidden should collapse — confirm the script's behavior and, if needed,
hide a card when all its showtime rows are hidden.

## Testing

- Unit test the grouping + packing helper (`lib/film-agenda.ts`):
  - groups events by resolved title;
  - sorts showtimes by `timeSortKey`;
  - orders films by earliest showtime;
  - packing balances columns and preserves left-to-right earliest-first order;
  - card height = 1 + showtime count;
  - both 3-col and 2-col packings produced.
- Visual verification via the browser at desktop / md / mobile widths on the
  `/ca/film` page, checking grid-line alignment and the 05:00 visibility script.

## Out of scope

- Changing any non-film category layout.
- A per-category layout config flag (deferred; trigger is hardcoded to `"film"`).
- Linking the title; per-showtime links cover the booking URLs.
