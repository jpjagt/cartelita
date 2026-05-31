# Cartelera — Design

**Date:** 2026-06-01
**Status:** Approved design, pre-implementation
**Polestar:** See [`MANIFESTO.md`](../../../MANIFESTO.md). Future directions live in
[`docs/future-features.md`](../../future-features.md).

## 1. Summary

Cartelera is a curated, navigable guide to a city's cultural life — small enough
to trust, broad enough to matter. It begins in Barcelona. It succeeds when a user
closes it and goes outside.

This document specifies the **MVP** and the domain/architecture foundations the
MVP is built on. It deliberately covers only what we build now; deferred
directions are recorded separately in `docs/future-features.md`.

## 2. Curation model

Curation is **source-level**: we hand-pick which venues are worth following, and
everything they produce is shown. A venue's presence on Cartelera is an implicit
recommendation. There is no per-event popularity ranking and no broad/catch-all
sources.

Per-event categorization still exists (an event must know what kind of thing it
is), but it is not editorial filtering — it is classification. The editorial work
is choosing venues.

## 3. Domain primitives

The model has four primitives plus a city scoping layer.

### Category
A kind of cultural event: `film`, `jazz`, `classical`, `theater` at launch.
Intrinsic to events. Categories are referenced by both venues and events.

### Venue
A place. A first-class citizen of the model (per Manifesto Principle 4 — places,
not transactions). A venue has:
- identity fields (name, address, city, optional site/URL)
- `categories: Category[]` — the categories this venue programs

A venue belongs to many lists, or one.

### Event
Something happening at a venue at a specific time. Attributes:
- `id`, `venue_id` (fk)
- `title`, `description?`, `image_url?`
- `start_date`, `start_time?`, `end_date?`, `end_time?`
- `price?` — **free text** (e.g. `"free"`, `"s.o."`, `"15€"`, `""`), never a
  number; venues express price as messy strings and parsing loses information
- `source_url` — the event's page; **deliberately non-unique** (a series page is
  shared across occurrences), so it carries no unique constraint by itself
- `external_id?` — stable per-event id from the source, used for dedup
- `recurrence_hint?` — **free text** display hint only (e.g. `"every Tuesday"`,
  `"monthly"`); no recurrence *logic*, no date expansion. The scraper emits one
  row per actual occurrence; this field just labels recurring ones in the UI
- `scraped_at`, `created_at`, `updated_at`
- `categories: Category[]` — **one or more** (m2m)

`title`, `description`, and `source_url` on the event are the **canonical
(default) content** — always present, in whatever language the scraper found.
Additional-language content lives in `EventTranslation` (see §4b). There is no
`lang` field on the event: nothing reads it (the canonical fields are simply the
fallback), so it is not stored.

### EventTranslation
Additional-language content for an event, scraped from that language's page:
- `event_id` (fk), `lang` (`'ca'` / `'es'` / `'en'`), `title`,
  `description?`, `source_url?`
- unique `(event_id, lang)`

A single-language venue emits **zero** translations (the event's canonical fields
suffice). A trilingual venue emits up to three, each scraped from its own
language page — **never machine-translated**. Locale resolution returns
title/description/source_url as a unit: `translation[locale] ?? event canonical`,
so a translated event also links to its own-language page.

**Dedup / upsert across nightly scrapes** — events have persistent identity; a
scrape upserts rather than wipe-and-reloads. Upsert key, in priority order:
1. `(venue_id, external_id)` — when the source exposes a stable id. Date-stable:
   a rescheduled event keeps its `external_id`, so its `start_date` is updated in
   place (no orphan, no duplicate).
2. `(venue_id, source_url)` — when there is no stable id.
3. `(venue_id, title, start_date)` — last resort. (Carries a small reschedule
   risk — a moved event may duplicate — accepted only on this degraded path.)

**Graceful degradation:** a venue's upsert runs in a transaction gated on scrape
success; on failure, that venue's existing rows are left untouched (never wiped).

**Categorization rule:**
- If a venue has exactly one category, all of its events inherit that category
  automatically (no per-event logic).
- If a venue has more than one category, that venue's scraper is responsible for
  emitting the correct category/categories per event, derived from source signals
  (URL section, DOM labels, keywords). Categorization lives at the source,
  because the signal needed to classify often exists only in the raw page and is
  gone once the event is normalized.

### List
An **authored collection of venues**, with an optional **per-venue category
whitelist** (which may also be set once for all venues in the list). A list's
view shows all events from the list's venues, in chronological order, filtered by
each venue's whitelist where present.

- A list has an `author`. For the MVP the only author is `cartelera`.
- The default homepage set = the cartelera-authored category lists (one per
  category). The "jazz" list = "these venues, showing only `jazz`-categorized
  events"; for a single-category jazz venue the whitelist is a no-op.
- The per-venue whitelist is what makes multi-category venues separable: a venue
  can sit in both the `film` list and the `expo` list, each showing only the
  matching events.

The `author` field and the list primitive are forward-compatible with
user/curator/group-authored lists, but **no list-creation, auth, or subscription
UI is built in the MVP.**

### City
A scoping layer present from day one. Venues belong to a city. Barcelona is the
only city at launch; the model does not hardcode it.

## 4. Recurrence

Recurrence is handled by **expansion at scrape time, not by a rule in the schema**.
The scraper emits **one event row per actual occurrence** (a weekly jam for the
next 8 weeks is 8 rows). The only recurrence artifact stored is the nullable
`recurrence_hint` free-text field on the event, used purely for a UI label/marker
(e.g. "every Tuesday"). There is no recurrence *logic*, enum, or date-expansion in
the application — the display is purely date-driven, matching the jazzin-style
"list each occurrence on its day" behavior.

Scraping consequence: a recurring event may live on a single series page or on
many per-edition pages. Either way the scraper normalizes both shapes into the
same flat per-occurrence event rows. (Occurrence *grouping* — a `series_key` /
`series` table linking occurrences — is deferred; see `docs/future-features.md`.)

## 4b. Languages (i18n)

Barcelona is trilingual, so the frontend supports **Catalan, Spanish, and
English**. The design rests on separating two kinds of text:

- **Chrome / UI text** (date headers, nav, empty states, **category names**) is
  finite and app-authored → **fully translated** via a per-locale string
  dictionary in the frontend. Locale-prefixed static routes (`/ca/...`,
  `/es/...`, `/en/...`) are pre-built — more pages at build time, which fits the
  static model at zero runtime cost. Date headers use the active locale.
- **Event content** (titles, descriptions, source_url) is source-authored →
  **kept in its original language, never machine-translated.** Where a venue
  *itself* publishes an event in multiple languages (common for institutional
  venues like CCCB/Filmoteca, each language on its own page), the scraper may
  capture those as `EventTranslation` rows (see §4 model). A single-language
  venue emits none, and the canonical event content is the fallback. Resolution:
  `translation[locale] ?? event canonical`.

Machine translation is never used. Capturing multi-language content is a
per-scraper choice, exercised only when a venue publishes it; the MVP's jazz
venue is single-language.

## 5. Architecture

Four concerns: scraper service, database, frontend, and a nightly orchestration
flow. Data plane runs on a Coolify server; presentation plane runs on a CDN/static
host.

**Languages:** the scraper/data service is **Python** (mature scraping ecosystem —
BeautifulSoup, httpx, Playwright; the language coding agents are most fluent in,
which serves the scraper-repair flow). The frontend is **Astro** (TypeScript). The
**Postgres schema is the single source of truth and cross-language contract**
between them: schema and migrations are owned by the Python side (where writes
happen); the Astro side gets typed read access (generated TS types from the DB, or
a typed query layer).

### Scraper service (Coolify, deployed from git)
- One scraper module per venue, behind a **uniform interface** (in the spirit of
  `getEventList()` → `getData(event)` → yields fully-categorized, normalized
  events).
- A scraper **emits events already categorized** (single-category venues emit
  their one category; multi-category venues contain their own classification
  logic).
- **Per-venue failure isolation**: one venue's scraper failing does not abort the
  run or corrupt other venues' data.
- **Graceful degradation**: on failure, retain the venue's last good data; never
  replace a category with an empty/broken result.
- **Structured run reporting**: per-venue success/failure, error detail, event
  count, last-success timestamp — surfaced via a notification channel (e.g. a
  Telegram bot) and usable for a health view.
- **Runnable in isolation**, locally and in the deployed environment, via the
  same code path as production (`run scraper X`).
- These properties make the service **repair-flow-ready** (human-in-the-loop,
  agent-assisted scraper repair) without coupling to any specific repair
  workflow, which is designed separately.

### Database — Postgres (Coolify)
- Relational source of truth. The many-to-many relationships (venues↔lists,
  events↔categories) are central to the model and modeled natively.
- Multi-city aware.
- Scheduled backups to object storage (Coolify's backup feature).

### API
- **None for the MVP.** There is no request-time dynamic read that needs a live
  API: the frontend regenerates statically after the nightly scrape, and there is
  no client-side personalization at launch.
- A standalone API is the documented extension point for when accounts, curator
  submissions, or other dynamic features arrive.

### Frontend (Astro, no Vercel)
- **Astro, `output: 'static'`**, deployed to any static/CDN host that is not tied
  to Vercel (e.g. Cloudflare Pages, Netlify, or the Coolify box itself). Ships
  near-zero JavaScript by default — the best fit for "fast server-rendered
  content, minimal JS" and the low-cost / zippy-load priority.
- **Server-side data fetching** against Postgres at build time (in Astro
  frontmatter / `getStaticPaths`). DB credentials are **server-only** (never
  `PUBLIC_`-prefixed, never bundled into client JS). The browser receives only
  rendered HTML.
- **Build-time slug enumeration is fine and aligned with the data lifecycle:** all
  slugs (category lists, later venue pages) are `cartelera`-authored and exist in
  the DB before the build; there is no runtime-created content needing instant
  URLs. New data appears via the nightly scrape, which *triggers* the rebuild — so
  build-time enumeration always sees current data.
- **Rebuild-on-scrape**, CDN-cached for fast loads.
- Default view: chronological "what's on now/today", day-by-day (jazzin-style),
  per Manifesto Principle 2 (tonight over someday).
- **No client-side persistence** in the MVP (no localStorage, no favorites, no
  accounts).
- *Future exit hatch (not MVP):* if user-created slugs ever arrive, Astro's
  on-demand rendering (`output: 'hybrid'` + Node/Cloudflare adapter) lets specific
  routes render per-request without build-time enumeration — a per-route change,
  not a framework migration, and it coincides with the deferred accounts/API work.

### Network & orchestration
- The frontend build must reach Postgres on the Coolify box: Postgres exposed over
  a TLS-protected port, locked down with strong credentials, `sslmode=require`,
  and ideally IP allowlisting. (If the frontend is built on the Coolify box, this
  is internal-network only.)
- **Nightly flow:** Coolify cron triggers the scrape → scrapers write to Postgres
  → scrape completion calls the frontend host's **build hook** (e.g. Cloudflare
  Pages / Netlify deploy hook, or a Coolify redeploy trigger) → Astro rebuilds
  statically from the DB once and is served CDN-cached until the next scrape.

## 6. MVP scope

**Launch categories:** `film`, `jazz`, `classical`, `theater`.

- Each category is backed by a curated, **credible-not-exhaustive** set of venues
  — the venues a knowledgeable local would expect to see. Completeness is not
  required; credibility is (Manifesto Principle 3). "Not exhaustive" is fine;
  "missing an obvious canonical venue" is not.
- **One deliberately multi-category venue** is included at launch (Filmoteca de
  Catalunya: core to `film`, also runs talks/cycles) to exercise the
  multi-category categorization + per-venue whitelist path end-to-end on real
  data.
- **One cartelera-authored list per category**, forming the default homepage set.
- Chronological day-by-day "what's on" view.
- Recurrence supported in schema and scrapers.

**Not in the MVP** (and why): no favorites / "my list" / localStorage (only worth
building once there are enough venues that filtering to favorites is useful); no
accounts; no user/curator/group-authored lists or list-creation UI; no standalone
API; no LLM categorization-filter layer (single- and multi-category scrapers
cover launch needs); no autonomous scraper auto-repair. See
`docs/future-features.md` for the fuller list and rationale.

## 7. Foundations that must hold from day one

These are cheap now and expensive to retrofit, so the MVP must respect them even
though no feature exercises them yet:

- **Venue is first-class** (its own entity with identity), not a column on events.
- **Events carry one or more categories**; the list primitive carries a per-venue
  category whitelist.
- **Lists have an author** (hardcoded `cartelera`).
- **City is a scoping layer** (Barcelona not hardcoded).
- **Recurrence** is in the event model.
