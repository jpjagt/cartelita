# Cartelera Deployment Design

**Date:** 2026-06-03
**Status:** Approved (pending spec review)
**Scope:** Deploy the MVP to a Coolify instance on a Hetzner server, with a nightly
scrape and a frontend rebuild. Frontend served at `cartelita.july.dev`.

## 1. Goal

Get the existing MVP (one+ venues, trilingual static site) running in production:

- **Postgres** on the Coolify box, reachable only on the internal network.
- **Scraper** runs nightly at **02:00** (`cartelera migrate && cartelera run all`).
- **Frontend** (Astro SSG) rebuilds nightly at **05:00**, reading Postgres at build
  time, and is served static at `https://cartelita.july.dev`.

No public API, no DB exposed to the internet, one platform (Coolify) to operate.

## 2. Topology

```
Hetzner box (Coolify)
├─ Postgres service             (internal network: host e.g. "postgres", db "cartelera")
├─ scraper app  (Dockerfile)    ── Coolify Scheduled Task @ 02:00 → cartelera migrate && run all
└─ web app      (Nixpacks/Node) ── Coolify Scheduled Task @ 05:00 → pnpm build → static dist
                                    served by Coolify proxy (Traefik) + auto-TLS at cartelita.july.dev
```

Both apps connect to Postgres over Coolify's **internal Docker network**, so
`DATABASE_URL` uses the internal service hostname and **no SSL** (`sslmode` not
required on the internal network). Postgres is never published to a public port.

## 3. Build method

### 3.1 Scraper — Dockerfile on Python 3.14

The scraper's correctness depends on **Python 3.14's stdlib HTML parser**.
Verified: the same Harlem Jazz Club fixture parses into **42 event cards on 3.14
but only 9 on 3.13** — `html.parser` (stdlib, part of CPython) changed its
handling of this site's markup between minor versions. Nixpacks tops out at 3.13,
so a buildpack build would **silently under-collect events**. We therefore build
the scraper from a Dockerfile pinned to the exact interpreter the code is
developed and tested on.

`scraper/Dockerfile`:

- `FROM python:3.14-slim`
- `apt-get install -y --no-install-recommends tesseract-ocr` (used by the
  `casa_figari` OCR scraper) and clean apt lists.
- Install `uv`, then `uv sync` (or `uv pip install .`) to install the project and
  its locked deps.
- Entry/command for the scheduled task: `cartelera migrate && cartelera run all`.
  (Coolify's scheduled task can override the command; the image just needs the
  `cartelera` console script on PATH.)

`requires-python` stays `>=3.14` (the design-verification edit to `>=3.13` was
reverted). No source changes are required for the scraper to deploy.

### 3.2 Web — Nixpacks (Node)

Node is unaffected by the Python parser issue, so the web app uses Coolify's
Nixpacks buildpack:

- `pnpm build` produces the static `dist/`.
- Coolify serves `dist/` as a static site and terminates TLS for
  `cartelita.july.dev`.

### 3.3 Web env fix (must fix)

`web/src/lib/db.ts` reads `import.meta.env.DATABASE_URL`. The module's own comment
and `AGENTS.md` say it must read **`import.meta.env.DATABASE_URL`** — Vite inlines
`import.meta.env.*` at build time, which is both a leak risk and unreliable for a
build-time-only secret. Change to `import.meta.env.DATABASE_URL`.

The existing `ssl: url.includes("localhost") ? false : "require"` would force SSL
for our internal (non-localhost) DB host, which won't offer SSL. Adjust so the
internal deployment connects **without** SSL (e.g. drive SSL from an explicit env
flag, defaulting off for the internal network). Internal-only traffic does not
need TLS.

## 4. Scheduling — Coolify Scheduled Tasks

Two scheduled tasks defined in Coolify (visible/manageable in the UI):

| Time  | App     | Command                                  |
|-------|---------|------------------------------------------|
| 02:00 | scraper | `cartelera migrate && cartelera run all` |
| 05:00 | web     | rebuild (Coolify redeploy / `pnpm build`)|

`migrate` is idempotent (filename-ordered, `CREATE TABLE IF NOT EXISTS`), so
running it before each scrape is safe and keeps the schema current on deploy.
`run all` isolates failures per venue and returns non-zero if any venue failed,
so the task's exit status surfaces problems without aborting other venues.

The 3-hour gap (02:00 → 05:00) comfortably covers scrape duration; the two stages
stay decoupled and independently observable.

## 5. Configuration / secrets

Set as Coolify environment variables (not committed):

- **Postgres service:** `POSTGRES_DB=cartelera`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.
- **scraper app:** `DATABASE_URL=postgresql://<user>:<pw>@<internal-host>:5432/cartelera`.
- **web app:** `DATABASE_URL=<same internal URL>` (build-time only; never
  `PUBLIC_`-prefixed, never in client JS).

The existing `ensure_database_exists()` path in `migrate` can create the DB if the
Postgres service starts empty, given a user with create-db rights; otherwise the
DB is created once via Coolify's Postgres provisioning.

## 6. Out of scope

- No public API, no DB public exposure, no Firebase/Cloudflare/Netlify.
- No CI pipeline beyond Coolify's git-push deploy.
- Backups: Coolify's Postgres backup feature can be enabled later (noted in the
  main spec); not configured here.
- Switching BeautifulSoup off `html.parser` (e.g. to lxml) is deliberately NOT
  done — it would change scraping behavior across every venue and require
  re-verifying all scrapers. Pinning 3.14 via Docker avoids that churn.
- Multi-city, accounts, favorites — unchanged from MVP scope.

## 7. Changes this introduces to the repo

1. `scraper/Dockerfile`: `python:3.14-slim` + apt `tesseract-ocr` + `uv` + project
   install; runs the `cartelera` CLI.
2. `scraper/.dockerignore`: exclude `.venv/`, `__pycache__/`, tests fixtures bloat,
   etc.
3. `web/src/lib/db.ts`: `import.meta.env.DATABASE_URL`; internal (no-SSL) connection.
4. Coolify-side (not in repo): two apps (scraper from Dockerfile, web from
   Nixpacks), one Postgres service, two scheduled tasks, env vars, domain
   `cartelita.july.dev`.
5. A short deploy section in the README / AGENTS.md documenting the Coolify setup.

`scraper/pyproject.toml` `requires-python` remains `>=3.14` (no change).
