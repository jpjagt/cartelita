# AGENTS.md — orientation for agents working on Cartelera

Read this first. It points you at the authoritative docs and records the
non-obvious conventions, invariants, and gotchas that aren't apparent from any
single file. For *what Cartelera is and why*, read `MANIFESTO.md`. For dev setup,
`README.md`.

## Where the design lives (read before changing the model or architecture)

- `docs/superpowers/specs/2026-06-01-cartelera-design.md` — the design: curation
  model, domain primitives, architecture, MVP scope, i18n. **The source of truth
  for intent.** If you're about to make a design-level decision, it's probably
  already decided here.
- `docs/future-features.md` — things deliberately **deferred** (favorites,
  accounts, user/curator lists, social, beacon hardware, multi-city, standalone
  API, autonomous scraper auto-repair). Don't build these without a conversation;
  each notes *why deferred* and *what foundation already supports it*.
- `docs/superpowers/plans/2026-06-01-cartelera-mvp-vertical-slice.md` — the
  task-by-task build plan for the current slice (mostly of historical interest now).

## Repo shape

- `scraper/` — Python 3.14 (managed by **`uv`**) data plane: Postgres schema +
  migration runner, SQLAlchemy models, per-venue scrapers, seed, upsert,
  orchestration CLI. Run things with `uv run` from `scraper/`.
- `web/` — **Astro** (static, **pnpm**) frontend reading Postgres at build time.
- The **Postgres schema is the cross-language contract.** Python owns/writes it
  (migrations in `scraper/migrations/`); Astro reads it. A model/query change on
  one side that doesn't match the schema is a bug.

## Conventions & invariants that bite if you don't know them

- **Prices are free text** (`"12€"`, `"s.o."`, `""`), never parsed to numbers.
  Same convention for **`event.language`** (`"VOSE"`, `"hy"`, `"non-verbal"`,
  NULL = unknown): display-only, never parsed or inferred.
- **A "source" and a "venue" are distinct.** A source is the unit of SCRAPING;
  a venue the unit of CURATION. `REGISTRY` maps `source_slug → (Scraper,
  SourceDefinition)`; most sources are 1:1 with a venue via the
  `register(scraper, venue)` sugar (unchanged for existing scrapers), while
  aggregators/social profiles use `register_source(...)` with several venues.
  A multi-venue source sets `venue_slug` on every ScrapedEvent; its venue list
  is its editorial whitelist and the runner fails fast on any event outside
  it. `cartelera run <slug>` takes source slugs. Sources have no DB table.
  **Exception — opt-out sources** (only `jazzin-amsterdam`, decided
  2026-10-13; rationale in its `_SOURCE.md`): the scraper also implements
  `scrapers.base.DiscoversVenues`, so any feed venue it neither overrides
  (`VENUES` aliases) nor denies (`DENIED`) is created at run time
  (`cartelera.discovery`; `venue.discovered_by` = the source), reported on a
  rolling `venue-review` GitHub issue, and reviewed after the fact. Exact name
  matching only, never fuzzy; a discovered slug something else owns is refused.
- **Cities**: `seed.CITIES` (scraper) and `web/src/lib/cities.ts` (locales,
  defaults — UI config lives web-side, not in Postgres) must both know a city.
  URLs are `/:city[/:locale[/:category]]`; bare `/` is the city selector.
  **List slugs are unique per city** (every city has its own "jazz" list), so
  lists are always addressed as (city, slug).
- **Events carry 1+ categories**; `category` is the model name and `categories`
  the column/relationship (no "tag" naming — that was renamed).
- **A "category" and a "list" are related but distinct.** A `List` is an authored
  collection of venues with an optional **per-venue category whitelist**
  (`list_venue.whitelist_category_id`, nullable = "all of the venue's events").
  The homepage category pages ARE cartelera-authored lists. Multi-category venues
  (e.g. Jamboree = jazz + club) sit in multiple lists, each whitelisted to one
  category — that's how their events split correctly. `list_venue` uses a
  surrogate PK + two partial unique indexes precisely because the whitelist is
  nullable (a composite PK can't include a nullable column in Postgres).
- **Event content lives canonically on `Event`** (`title`/`description`/`source_url`);
  there is **no `lang` column**. Additional languages go in `EventTranslation`
  (one row per extra language, scraped from that language's own page) and resolve
  as `translation[locale] ?? canonical`. The frontend chrome (dates, nav,
  **category names**) is translated via `web/src/i18n/`; event content is NOT
  machine-translated.
- **`annotations TEXT[]`** on Event is a catch-all bag of free-form labels (a
  venue's genre tags etc.). Not used for filtering yet — preserved for the future.
- **Recurrence = the scraper emits one row per occurrence.** No expansion logic;
  the only artifact is the free-text `recurrence_hint` display label.
- **Dedup is per-venue upsert** (not wipe-and-reload), keyed by
  `(venue_id, external_id)` → `(venue_id, source_url)` → `(venue_id, title, start_date)`.
  Tiers 2/3 are best-effort; a scraper should supply a stable `external_id` or a
  per-event `source_url`.
- **Nothing is deleted; cancelled events are hidden.** After a *healthy* run,
  a venue's upcoming events the run didn't return count `missed_runs`; at 3
  they get `hidden_at` (un-hidden if they reappear). Every event query must
  filter `hidden_at IS NULL`. **Null guard:** an upsert never overwrites a
  stored value with `None`/empty (prices, times, description, image, language,
  annotations, translations…) — a run can change a value, never blank it.
- **`City` is a scoping layer** — Barcelona, Yerevan and Amsterdam exist; all queries
  (web + `queries.py`) are city-scoped. Yerevan's design doc:
  `docs/superpowers/specs/2026-08-18-multi-city-yerevan-design.md`; its
  venue/genre research: `docs/yerevan.md`.
- Never add a `PUBLIC_`-prefixed DB var.
- **Adding a category a scraper emits but seed doesn't define fails fast** with
  `unknown category slug '...'` — that's intentional. Add it to `seed.py`'s
  `CATEGORIES` and wire its list/whitelist.

## Adding or fixing a scraper

Use the **`writing-a-scraper`** skill (`.claude/skills/writing-a-scraper/`). It's
not optional process decoration — it encodes a real lesson: the first Jamboree
scraper passed its tests while silently dropping price for ~160 events and
mislabeling club nights, because it trusted JSON-LD that lacked those fields. The
skill's non-negotiable step is **verifying scraper output against the live site
field-by-field** (via the `browser-use` skill). Each scraper has a
`<venue>_SOURCE.md` next to it recording where each field comes from; write one.
`scraper/src/cartelera/scrapers/jamboree.py` + `jamboree_SOURCE.md` are the
worked example (note: parse the venue's **list/`llista` view DOM**, not just
JSON-LD; the genre tags are too granular for top-level category — derive category
from a real discriminator and put genres in `annotations`).

## Current state (as of 2026-10-10)

- **Live at https://cartelita.july.dev**, deployed from `main` on Coolify.
  Three cities: Barcelona (45 per-venue scrapers), Yerevan (per-venue +
  the `tomsarkgh` aggregator) and Amsterdam (one multi-calendar source,
  `jazzin_amsterdam`, ~160 venues). Both test suites:
  `cd scraper && uv run pytest`; `cd web && pnpm test`.
- **Favourites are browser-only** (localStorage, `web/src/lib/favourites.ts`):
  star a venue from the margin next to any event row (hover) or from the
  My list venue directory; `/:city/:locale/my-list` ships the city's whole
  curated agenda and filters it client-side (`data-filtered` rows, handled by
  `syncAgenda`). No accounts/social — see `docs/future-features.md`.
- **Adding venues needs no architecture change** — a scraper module +
  `SOURCE.md` + its venue definitions (categories, list memberships with
  whitelists). Follow the skill.

## Deploy & prod access

Read `docs/deploy.md` for the full setup. The short version:

- **Pushing `main` deploys.** Coolify rebuilds the `cartelita-scraper`
  (Dockerfile, `scraper/`) and `cartelita-web` (Nixpacks static site, `web/`)
  apps on push; the web build reads the prod DB at build time, so a web deploy
  is how new data gets published.
- **Nightly:** a Coolify scheduled task on the scraper runs
  `cartelera migrate && cartelera run all` at 02:00 (`run` seeds first, so new
  cities/venues/lists appear on their first scrape); the `cartelita-redeploy`
  container (`deploy/redeploy-cron/`) redeploys the web app at 05:00.
- **Shell into prod containers** over SSH (key-restricted agent account):

  ```
  ssh coolify-agent list                  # "<uuid>-<deploy-id>  <stack>" per container
  ssh coolify-agent <uuid> "<cmd>"        # run <cmd> in that container
  ```

  Pass the **bare uuid** (the part before the last `-<digits>`), e.g.
  `ssh coolify-agent <scraper-uuid> "cartelera run jazzin-amsterdam"`. The full
  name printed by `list` is rejected (`invalid target`). Right after a deploy
  the old and new containers briefly coexist and the bare uuid answers
  `ambiguous` — wait for the old one to stop.
- **Publish fresh data now** (instead of waiting for 05:00): run the scrape in
  the scraper container, then trigger a web redeploy through the redeploy
  container's own credentials:

  ```
  ssh coolify-agent <redeploy-uuid> 'curl -fsS -X POST -H "Authorization: Bearer $COOLIFY_TOKEN" "https://$COOLIFY_SERVER/api/v1/deploy?uuid=$WEB_APP_UUID&force=true"'
  ```

  A web deploy that overlaps a running scrape builds from half-written data;
  redeploy again once the scrape finishes.
- Prod Postgres is the `cartelita-postgresql` target (internal network only).

## Scraper health

Each `cartelera run` classifies every source (healthy / degraded / broken /
site_down), records a `scrape_run`, and opens/closes a GitHub issue per bad
source — the repair queue. Design and thresholds:
`docs/superpowers/specs/2026-10-12-scraper-health-design.md`; code in
`scraper/src/cartelera/health.py` (pure: constants, rules, state machine) and
`health_ops.py`. CLI: `cartelera health`, `cartelera health ack <source>`
(legit change, e.g. season break: also hides the upcoming events that run
didn't see). Coverage counts only events the previous healthy/acked run saw. If you're repairing a scraper from a health
issue: follow the `writing-a-scraper` skill, and note a degraded verdict often
means a *partial* break (pagination stopping early, a dead field selector).

## Gotchas

- `browser-use` CLI 3.x lost `--session` isolation and attaches to the user's
  real Chrome (interactive approval required) — scraper recon/verification is
  HTTP-first now; see the writing-a-scraper skill's Phase 1 caveat.
- The migration runner pre-creates `schema_migrations`, so its SQL uses
  `CREATE TABLE IF NOT EXISTS`. Migrations are applied in filename order and are
  idempotent; reset a dev/test DB with
  `psql <db> -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"`.
- The frontend build needs `DATABASE_URL` in its env (`DATABASE_URL=... pnpm build`).
