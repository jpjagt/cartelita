# Multi-city support (Yerevan) — design

Date: 2026-08-18. Extends the 2026-06-01 cartelera design; that doc remains the
source of truth for everything not touched here (curation model, lists,
translations, upsert tiers). Yerevan-specific venue/genre research lives in
`docs/yerevan.md`.

## Goal

Run Cartelita in a second city (Yerevan) on the same codebase and database:
city-scoped URLs, city-specific locales (`hy`/`ru`/`en`), and a scraper
architecture that handles Yerevan's reality — aggregator sites covering many
venues, and venues that publish only to Instagram.

## Decisions (settled in discussion)

- URL order is **city first**: the city is the product scope and determines the
  available locales.
- Old Barcelona URLs (`/ca/jazz`) are **not** redirected; breakage accepted.
- Bare `/` becomes a **city selector**: a bare page, grid layout, cities in a
  centered vertical list.
- Event performance/source language is modeled as **display-only free text**
  (the price convention), not structured data.
- City→locale config lives in **web code** (`cities.ts`), not the DB.
- **Source vs venue split**: a Source is the unit of scraping, a Venue the unit
  of curation. One source feeds 1..N venues.
- Armenian's locale code is **`hy`** (not `am`).

## 1. Sources vs venues (scraper architecture)

Today `REGISTRY` maps `venue_slug → (Scraper, VenueDefinition)` — scraping and
curation are conflated 1:1. Yerevan breaks this: `tomsarkgh.am` is one site
covering many venues (the only realistic path to the JS-rendered/403
institutional sites), and each Instagram profile is a source too.

Changes in `scraper/`:

- New `SourceDefinition` in `types.py`:

  ```python
  class SourceDefinition(BaseModel):
      slug: str
      name: str
      venues: list[VenueDefinition]   # >= 1
  ```

- `REGISTRY` becomes `source_slug → (Scraper, SourceDefinition)`.
- **Compat sugar:** `register(scraper, venue: VenueDefinition)` keeps working,
  wrapping the venue in a single-venue `SourceDefinition` whose slug is the
  venue slug. Existing Barcelona scraper files need no edits. A
  `register_source(scraper, source)` variant is added for multi-venue sources.
- `ScrapedEvent` gains `venue_slug: str | None = None`. `None` is allowed only
  when the source has exactly one venue (the runner fills it in); a multi-venue
  source must set it on every event, and the runner fails fast on an event
  whose `venue_slug` is not among the source's venues.
- The runner groups a source's events by venue and applies the **existing
  per-venue upsert unchanged** — dedup keys `(venue_id, external_id)` etc. are
  untouched. One source failing marks all its venues' data stale together.
- `ScrapeResult.venue_slug` is renamed `source_slug`.
- `cartelera run <slug>` takes source slugs.
- An aggregator source's venue list **is its whitelist**: events for venues not
  in its `SourceDefinition` are dropped by the scraper. Curation stays
  editorial; the aggregator just moves bytes.
- `SOURCE.md` files are per source (one for `tomsarkgh`, covering its field
  mapping once).
- **No `source` DB table.** Sources are a code-level orchestration concept; the
  DB stays venue-centric. Revisit only if something needs to query by source.

## 2. Web: multi-city routing

```
/                          city selector (bare grid page, vertical centered city list)
/:city                     city homepage, city's default locale
/:city/:locale             city homepage, explicit locale
/:city/:locale/:category   category page
```

Locale is required whenever a category is in the path — this avoids the
`/yerevan/ru` vs `/yerevan/jazz` single-segment ambiguity that
`/:city/:locale?/:category?` would create.

- `web/src/lib/cities.ts`:

  ```ts
  export const CITIES = {
    barcelona: { locales: ["ca", "es", "en"], defaultLocale: "ca", defaultList: "jazz" },
    yerevan:   { locales: ["hy", "ru", "en"], defaultLocale: "hy", defaultList: "jazz" },
  } as const
  ```

  This replaces the global `LOCALES` / `DEFAULT_LOCALE` / `DEFAULT_LIST`
  consts. `Locale` union becomes `ca | es | en | hy | ru`.
- Pages move to `pages/index.astro` (selector), `pages/[city]/index.astro`,
  `pages/[city]/[locale]/index.astro`, `pages/[city]/[locale]/[list].astro`;
  `getStaticPaths` walks `CITIES`. One build emits all cities.
- Build-time queries gain a **city filter** (first real use of the `City`
  scoping layer — today they implicitly fetch everything).
- `i18n/index.ts` gains `hy` and `ru` dictionaries; all locales gain `folk` and
  `rock` category names. Armenian is the first non-Latin script through the
  UI — verify the font stack and any `text-transform` styling render it
  properly. Category slugs stay English, so URLs are unaffected.
- OG image generation keys on (city, locale, list) paths; follow the existing
  scheme with the city prefix.

## 3. Schema: two additive migrations

- `event.language TEXT NULL` — display-only free text on the price convention:
  scraper emits a concise string only when the source states it (`"VOSE"`,
  `"hy"`, `"ru"`, `"non-verbal"`), `NULL` = unknown, never parsed or inferred.
  Mirrored as `language: str | None = None` on `ScrapedEvent`; rendered as a
  small label on event rows when present. Motivation: a visitor in Yerevan
  needs to know whether they'll understand the performance.
- `venue.instagram_url TEXT NULL` — mirrored on `VenueDefinition`. Serves venue
  display and points the IG ingest path at the right profile.

## 4. Seed

- `CITIES = [("barcelona", "Barcelona"), ("yerevan", "Yerevan")]` in `seed.py`;
  venues attach via their existing `city_slug`.
- `CATEGORIES` gains `folk` and `rock`. Nothing is dropped: categories are
  global, lists are per-city, so Yerevan simply never gets `flamenco`/`pop`
  lists while Barcelona keeps them.
- Seed iterates sources and upserts each source's venues.

## 5. Yerevan initial sources

Per `docs/yerevan.md`. First wave, conventional scrapers (each venue via its
own site or its esora per-source page, 1:1): **Ulikhanyan** (jazz),
**Malkhas** (jazz), **Moscow Cinema** (film, whitelist), **Cinema House**
(film), **Komitas Chamber Music House** (classical), **Pantomime Theatre**
(theater), **Arten** (theater, cross-genre). Second wave: the **tomsarkgh**
multi-venue source for the institutional houses (Philharmonic, Opera, state
theatres — whitelisted). Third wave: IG sources (**Tonelab**, **Hayfilm**,
**Karin**'s dance nights). Each still follows the writing-a-scraper skill.

## 6. Instagram ingest

There is no official API for public profiles we don't own (Basic Display API
shut down Dec 2024; Graph API needs the account holder's authorization), and
anonymous profile access is login-walled. Approach:

- A shared `instagram.py` helper in `scrapers/` (added to
  `_NON_SCRAPER_MODULES`): given a profile handle, drives a **logged-in
  browser session** to pull recent posts, then extracts `ScrapedEvent` fields
  from caption + flyer image via Claude with vision (flyers often carry the
  only structured info, in Armenian/Russian).
- Per-venue IG scrapers are thin: handle + default category + prompt hints.
- Rules: `external_id` = IG post shortcode (stable dedup for free); no
  confident date → skip the post (silence over noise); `language`/`price` only
  when stated; nightly, low volume, one session — shaped like a person.
- Fallback if account bans become a nuisance: a paid scraper API (Apify et
  al.), swapped in behind the same helper interface.
- Isolated by design: everything downstream sees ordinary `ScrapedEvent`s.

## 7. Testing

- Scraper: unit tests for the registry sugar (single-venue wrap), runner
  grouping/fail-fast on multi-venue sources, and seed with two cities. Existing
  per-scraper fixture tests unchanged.
- Web: extend existing tests to city-scoped paths; a build with Barcelona data
  plus one hand-seeded Yerevan venue verifies routing, locale fallbacks, and
  Armenian rendering end-to-end.
- IG extraction: fixture posts (caption + flyer image) with expected
  `ScrapedEvent` output; live verification per the writing-a-scraper skill.

## 8. Build order

1. Source/venue registry refactor (pure refactor, Barcelona must stay green).
2. Schema migrations + `ScrapedEvent` fields.
3. Multi-city web (cities.ts, routes, city selector, hy/ru dictionaries) —
   verifiable with a hand-seeded Yerevan venue.
4. First conventional Yerevan scrapers (Ulikhanyan first: easiest source).
5. tomsarkgh multi-venue source.
6. IG ingest subsystem (riskiest, last).

## Out of scope

Machine translation of event content, the `art` category, per-city OG theming,
a `source` DB table, URL redirects from the old Barcelona structure, city
selector beyond the bare grid page.
