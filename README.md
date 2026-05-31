# Cartelera

A curated, navigable guide to a city's cultural life. Starts in Barcelona.

See `MANIFESTO.md` (philosophy), `docs/superpowers/specs/` (design), and
`docs/future-features.md` (deferred directions).

## Layout
- `scraper/` — Python data plane: schema, models, per-venue scrapers, orchestration.
- `web/` — Astro static site reading Postgres at build time.

## Dev setup
Requires PostgreSQL running locally, `uv`, and `pnpm`.

```bash
createdb cartelera_dev
createdb cartelera_test
cd scraper && uv sync --extra dev
cp .env.example .env
uv run cartelera migrate
uv run cartelera seed
uv run cartelera run all
cd ../web && pnpm install && cp .env.example .env && pnpm dev
```
