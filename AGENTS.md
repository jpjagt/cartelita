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
- **`City` is a scoping layer** — Barcelona is not hardcoded, but it's the only
  city now.
- **DB credentials are server-only.** `web/src/lib/db.ts` reads
  `process.env.DATABASE_URL` (NOT `import.meta.env`, which Vite would inline).
  Never add a `PUBLIC_`-prefixed DB var.
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

## Current state (as of 2026-06-01)

- **Live: one venue (Jamboree), two categories (jazz + club).** The full pipeline
  works end-to-end: `cartelera migrate && seed && run jamboree` → ~247 events in
  Postgres → `pnpm build` → trilingual static pages. Both test suites green
  (`cd scraper && uv run pytest`; `cd web && pnpm test`).
- **Not yet done:** the work is on a feature branch, **not merged or deployed.**
  The Coolify deploy + nightly cron + frontend build-hook are *designed in the
  spec but not built*. There is no standalone API (frontend reads Postgres at
  build time). No favorites/accounts/social.
- **Adding venues is the expected next work** and needs no architecture change —
  it's a scraper module + `SOURCE.md` + seed rows (venue, its categories, its list
  memberships with whitelists). Follow the skill.

## Gotchas

- `browser-use`'s daemon occasionally times out on first launch — `browser-use
  close` then retry. `close` when done.
- The migration runner pre-creates `schema_migrations`, so its SQL uses
  `CREATE TABLE IF NOT EXISTS`. Migrations are applied in filename order and are
  idempotent; reset a dev/test DB with
  `psql <db> -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"`.
- The frontend build needs `DATABASE_URL` in its env (`DATABASE_URL=... pnpm build`).
