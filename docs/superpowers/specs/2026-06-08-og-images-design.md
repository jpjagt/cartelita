# Build-time OG images — design

Date: 2026-06-08
Status: approved

## Problem

Each `[locale]/[list]` page should expose a social-share (Open Graph) image that
looks like the live agenda — the graph-paper grid with the wordmark, genre nav,
and a few days of events — so links unfurl into a recognizable preview instead of
a blank card.

The live page's grid layout depends on client-side JS (`syncGrid` in
`Layout.astro` sets `--cell`/`--col-start`/`--band-cells`; `Navbar`'s `layoutNav`
places genre links). The OG image also has **different layout rules** than the
live page, so it is a *dedicated render*, not a screenshot of the real page.

## Goals

- One 1200×630 PNG per `[locale]/[list]` page, generated at build time.
- Visually matches the live look (dark theme, graph-paper grid, genre colors).
- Referenced from each page's `<head>` via `og:image` (+ Twitter card meta).

## Non-goals

- Per-request / dynamic OG generation.
- Pixel-perfect identity with the live responsive layout (the OG layout is its
  own fixed spec).
- Other image sizes / aspect ratios (1200×630 only — universal, never cropped).

## Decisions

- **Renderer: Node script + Playwright (headless Chromium).** The look is built
  on one big CSS grid; only a real browser renders `display: grid` correctly.
  Satori/Pillow would mean a hand-ported parallel layout that drifts. Chosen for
  one source of truth for the visual language.
- **Dimensions: 1200×630 (1.91:1).** Universal Open Graph size, never cropped by
  Twitter/WhatsApp/Slack/Discord/LinkedIn/Facebook.
- **Content: fill the canvas, clip overflow.** Render days/events top to bottom
  until ~630px is consumed; the rest is cut off (like the live screenshot).
- **Genre nav: `[active] + [jazz, classic, theater, film] + [andMore]`,** with the
  active genre removed from the fixed four (dedup), localized names, and slugs
  that aren't real DB lists silently skipped. No locale switcher.
- **Slug→name mapping:** the DB list slug is `classic` but the i18n category key
  is `classical`; the builder maps `classic`→`classical` for display.

## Components

### 1. `web/src/lib/og-template.ts` — pure HTML builder

`renderOgHtml({ locale, list, lists, days }) → string`

Returns a full standalone HTML document (inlined CSS, **no external JS**) that
reuses the visual language of `global.css` but with OG-specific rules as static
inline styles. Forced dark theme (the `.dark` palette) to match the screenshot.

- Canvas: 1200×630, `body` is one `display: grid`,
  `grid-template-columns: repeat(26, 1fr)`, `grid-auto-rows` ≈ cell height.
- **Header row(s):** "Cartelita" wordmark (left) + genre nav. Genre items:
  active first, then `jazz, classic, theater, film` minus the active slug, then
  the `andMore` string. Names via `categoryName(locale, slugForName(slug))`
  where `slugForName("classic") === "classical"`. Skip any slug not present in
  `lists`. Active item carries the genre fill (`cell-genre` equivalent).
- **Day header:** full-band shaded row with the localized long date
  (`weekday, day month`, via `localeTag`).
- **Event row column spans** (26 cols, 1-based; right fields anchored to the end
  via negative line numbers so they're exact regardless of title length):
  - time: `1 / span 2`
  - title: `3 / -9` (fills the slack; the `-9` leaves 1 padding col before venue)
  - venue: `-9 / span 6`
  - price: `-3 / span 2`
- **Overflow:** body `overflow: hidden`; rows past 630px are clipped.
- **Empty state:** when `days` is empty, render the localized "no events" line in
  the band (still a valid PNG).

This unit does one thing: data → HTML string. It is fully testable without a
browser.

### 2. `web/scripts/og.mjs` — render script

Run **after** `astro build`. Steps:

1. Connect to Postgres via the same `DATABASE_URL` the build already uses.
2. For each `locale × list` (from `LOCALES` and `getCategoryLists()`):
   `getEventsForList(list, locale)` → `groupEventsByDay()` →
   `renderOgHtml({ locale, list, lists, days })`.
3. Launch one Chromium instance. Per page:
   `page.setViewportSize({ width: 1200, height: 630 })`,
   `page.setContent(html, { waitUntil: "load" })`,
   `page.screenshot({ path: dist/og/<locale>-<list>.png })`.
4. Close the browser; close the DB connection.

Imports the shared lib and data layer (run via `vite-node` or compiled, matching
how the project already runs TS — see Open questions).

### 3. `web/src/components/Layout.astro` — meta tags

Add an optional `ogImage` prop. Emit in `<head>`:

- `<meta property="og:image" content={new URL(ogImage, Astro.site).href}>`
- `<meta property="og:image:width" content="1200">`
- `<meta property="og:image:height" content="630">`
- `<meta property="og:title" content={title}>`
- `<meta property="og:description" content={...}>`
- `<meta name="twitter:card" content="summary_large_image">`

`[locale]/[list].astro` passes `ogImage={`/og/${locale}-${list}.png`}`.

### 4. `web/src/i18n/index.ts` — strings

Add `andMore` to `Strings` and each locale: `ca: "i més"`, `es: "y més"` →
`es: "y más"`, `en: "and more"`.

## Data flow

```
astro build  →  dist/ (pages already contain <meta og:image="/og/..">)
node scripts/og.mjs
  → DATABASE_URL → getCategoryLists / getEventsForList → groupEventsByDay
  → renderOgHtml → Playwright screenshot → dist/og/<locale>-<list>.png
```

## Nixpacks / deployment

- Add `playwright` to `web/package.json` devDependencies.
- `nixpacks.toml`: provide Chromium's system libs and install the browser
  (`pnpm exec playwright install --with-deps chromium`) in the install/build
  phase; append `node scripts/og.mjs` to the build command after `astro build`.
- Tradeoff (accepted): ~300MB Chromium added to the build image; DB access at
  build time (already required by the existing build).

## Error handling

- No events for a page → render the empty state; still output a valid PNG.
- Chromium launch failure → fail the build loudly (don't ship pages whose
  `og:image` points at a missing file).
- Genre slug not a real DB list → silently skipped.

## Testing

- **Unit (Vitest, no browser)** on `renderOgHtml`:
  - genre order: active first, the fixed four deduped, `andMore` last;
  - `classic`→`classical` name mapping;
  - no locale switcher present in output;
  - correct event-row grid-column spans;
  - locale-specific strings (date heading, `andMore`, empty state).
- **Manual verify:** run the script locally, eyeball a generated PNG against the
  live screenshot.

## Open questions

- How to run the TS data layer from `scripts/og.mjs` on the build box — reuse
  `vite-node` (already a devDep) vs. a small build step. Resolve in the plan.
