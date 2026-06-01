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
createdb cartelera_test       # used by the Python test suite
cd scraper && uv sync --extra dev
cp .env.example .env          # sets DATABASE_URL=postgresql://localhost:5432/cartelera_dev
uv run cartelera migrate
uv run cartelera seed
uv run cartelera run jamboree  # or: run all
cd ../web && pnpm install && cp .env.example .env
pnpm dev   # reads DATABASE_URL from .env; use pnpm build for a static build
```

The Astro frontend (both `pnpm dev` and `pnpm build`) reads `DATABASE_URL` from
`web/.env` at build time — make sure that file exists before running either command.

### Running tests

```bash
# Python
cd scraper && uv run pytest

# Frontend
cd web && pnpm test
```
