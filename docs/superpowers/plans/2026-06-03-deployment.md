# Cartelera Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the Cartelera MVP to Coolify on Hetzner — a Dockerized Python scraper (nightly 02:00), an Astro static frontend built nightly (05:00) and served at `cartelita.july.dev`, both reading an internal-network Postgres.

**Architecture:** Scraper builds from a `python:3.14-slim` Dockerfile (the stdlib HTML parser behaves differently on 3.13, so the version must be pinned). Web builds via Coolify's Nixpacks (Node) into a static `dist/`. Postgres is a Coolify service on the internal Docker network; neither app exposes it publicly. Two Coolify Scheduled Tasks drive the nightly scrape and rebuild.

**Tech Stack:** Python 3.14 + uv, Docker, Astro 5 (SSG) + pnpm, PostgreSQL, Coolify (Traefik proxy, Nixpacks, Scheduled Tasks).

**Environment note:** Docker is **not** available in the dev sandbox, so `docker build` cannot be verified locally — those checks happen on the Coolify box (Task 5). Local verification is limited to file content, `pyproject`/lock integrity, and the web build.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `scraper/Dockerfile` (create) | Pin Python 3.14, install tesseract + uv + project, expose `cartelera` CLI |
| `scraper/.dockerignore` (create) | Keep the build context small / reproducible |
| `web/src/lib/db.ts` (modify) | Read `DATABASE_URL` from `import.meta.env`; no SSL on internal network |
| `docs/deploy.md` (create) | Operator runbook for the Coolify setup (the non-code half of the deploy) |

---

## Task 1: Scraper Dockerfile

**Files:**
- Create: `scraper/Dockerfile`
- Create: `scraper/.dockerignore`

- [ ] **Step 1: Write `scraper/.dockerignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
src/cartelera/scrapers/certs/
```

- [ ] **Step 2: Write `scraper/Dockerfile`**

Uses uv's official image to get a reproducible `uv` binary, installs tesseract for the `casa_figari` OCR scraper, and installs the project from the lockfile. The build context is the `scraper/` directory (set Coolify's "Base Directory" to `scraper`).

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.14-slim

# tesseract-ocr is required by the casa_figari OCR scraper (pytesseract).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# uv: copy the static binary from the official image (no pip bootstrap needed).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached) from the lockfile, then the project.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Now copy the source and install the project itself (provides the `cartelera` script).
COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Default command; the nightly Coolify Scheduled Task overrides/wraps this with
# `cartelera migrate && cartelera run all`.
CMD ["cartelera", "run", "all"]
```

- [ ] **Step 3: Verify the lockfile is current (local, no Docker needed)**

Run: `cd scraper && uv lock --check`
Expected: exits 0 (`Resolved … packages` / no "lockfile out of date"). If it fails, run `uv lock` and commit the updated `uv.lock` as part of this task.

- [ ] **Step 4: Sanity-check the Dockerfile references**

Run: `cd scraper && test -f uv.lock && test -f pyproject.toml && grep -q 'cartelera = "cartelera.run:main"' pyproject.toml && echo OK`
Expected: `OK` (confirms the files the Dockerfile COPYs exist and the `cartelera` console script is defined, so `CMD ["cartelera", ...]` resolves).

- [ ] **Step 5: Commit**

```bash
git add scraper/Dockerfile scraper/.dockerignore scraper/uv.lock
git commit -m "build: add scraper Dockerfile (python 3.14 + uv + tesseract)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Fix `web/src/lib/db.ts` env source + internal SSL

**Files:**
- Modify: `web/src/lib/db.ts`

The module comment already says to read `import.meta.env` (not `import.meta.env`, which Vite inlines), but the code does the opposite. Internal-network Postgres has no TLS, so SSL must default off and only turn on when explicitly requested.

- [ ] **Step 1: Replace the body of `web/src/lib/db.ts`**

```typescript
import postgres from "postgres"

// Server-only secret: read from the Node import.meta.env, NOT import.meta.env
// (Vite inlines import.meta.env.* at build time, which could bake the
// credential into output if this module were ever imported client-side).
const url = import.meta.env.DATABASE_URL
if (!url) throw new Error("DATABASE_URL is not set (server-only)")

// The production DB lives on Coolify's internal Docker network with no TLS, so
// SSL is off by default. Set DATABASE_SSL=require to force TLS (e.g. if the DB is
// ever reached over a public, TLS-terminated port).
const ssl = import.meta.env.DATABASE_SSL === "require" ? "require" : false

// One connection for the build process.
export const sql = postgres(url, { ssl })
```

- [ ] **Step 2: Type-check / build does not regress (local)**

Run: `cd web && pnpm test`
Expected: PASS (the existing `agenda.test.ts` / `i18n.test.ts` don't import `db.ts`, so they must stay green — this confirms no syntax/type breakage was introduced).

- [ ] **Step 3: Verify `import.meta.env.DATABASE_URL` is gone**

Run: `cd web && ! grep -rn "import.meta.env.DATABASE_URL" src && echo OK`
Expected: `OK` (the Vite-inlined read is fully removed).

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/db.ts
git commit -m "fix(web): read DATABASE_URL from import.meta.env; SSL off on internal net

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Local end-to-end build smoke test (proves the web change works against a real DB)

**Files:** none (verification only)

This proves the `db.ts` change actually connects and builds, using the local dev Postgres from the README (`cartelera_dev`). No source changes.

- [ ] **Step 1: Confirm the dev DB is reachable and seeded**

Run:
```bash
cd scraper && DATABASE_URL=postgresql://localhost:5432/cartelera_dev uv run cartelera migrate
```
Expected: `applied: …` (or "none (up to date)") with no connection error. If the DB doesn't exist, `migrate` creates it; then run `uv run cartelera seed` and `uv run cartelera run jamboree` to populate at least one venue.

- [ ] **Step 2: Build the frontend with DATABASE_URL from import.meta.env**

Run:
```bash
cd web && DATABASE_URL=postgresql://localhost:5432/cartelera_dev pnpm build
```
Expected: build succeeds; `dist/` is produced. This confirms `import.meta.env.DATABASE_URL` is read at build time and the no-SSL localhost connection works (proving the Task 2 change end-to-end).

- [ ] **Step 3: Confirm static output exists**

Run: `cd web && test -d dist && find dist -name '*.html' | head && echo OK`
Expected: lists at least one `.html` page and prints `OK`.

No commit (verification only).

---

## Task 4: Operator runbook `docs/deploy.md`

**Files:**
- Create: `docs/deploy.md`

Captures the non-code half of the deploy so it's reproducible. This is documentation; verification is a content check.

- [ ] **Step 1: Write `docs/deploy.md`**

````markdown
# Deploying Cartelera to Coolify

Target: Coolify on a Hetzner box. Frontend served at `https://cartelita.july.dev`.
Postgres stays on Coolify's internal Docker network — never published publicly.

## 1. Postgres service

1. In the Coolify project, add a **PostgreSQL** service.
2. Set `POSTGRES_DB=cartelera`, a strong `POSTGRES_USER` / `POSTGRES_PASSWORD`.
3. Note the **internal hostname** Coolify assigns (e.g. `postgres` or the service
   name). The internal connection string is:
   `postgresql://<user>:<password>@<internal-host>:5432/cartelera`
4. Do NOT expose a public port.

## 2. Scraper app (Dockerfile)

1. Add a new **Application** from this git repo.
2. Build Pack: **Dockerfile**. **Base Directory:** `scraper`.
   (So the build context is `scraper/`, matching the Dockerfile's COPY paths.)
3. Environment variables:
   - `DATABASE_URL=postgresql://<user>:<password>@<internal-host>:5432/cartelera`
4. This app has no web port — it's a worker driven by a scheduled task (below).
   Disable any health check / port mapping.

## 3. Web app (Nixpacks, static)

1. Add another **Application** from the same repo.
2. Build Pack: **Nixpacks**. **Base Directory:** `web`.
3. Build command: `pnpm build`. Output / publish directory: `dist`.
   Set it as a **static site** so Coolify serves `dist/` via its proxy.
4. Environment variables (build-time):
   - `DATABASE_URL=postgresql://<user>:<password>@<internal-host>:5432/cartelera`
   - (Do NOT set `DATABASE_SSL`; internal network is plain TCP.)
5. Domain: `cartelita.july.dev` (Coolify provisions TLS via Let's Encrypt).
   Point the `cartelita` DNS record at the Hetzner box first.

## 4. Scheduled tasks

In Coolify, add two Scheduled Tasks (cron, server timezone):

| Schedule (cron) | App     | Command                                  |
|-----------------|---------|------------------------------------------|
| `0 2 * * *`     | scraper | `cartelera migrate && cartelera run all` |
| `0 5 * * *`     | web     | redeploy (trigger a rebuild)             |

- The 02:00 scraper task runs `migrate` (idempotent) then `run all`. Its exit
  code is non-zero if any venue failed — check task logs.
- The 05:00 web task triggers a redeploy so Astro rebuilds the static site from
  the freshly-scraped DB. (If Coolify's scheduled task can't trigger a redeploy
  directly, use the app's **deploy webhook**: `curl -fsS <deploy-webhook-url>`.)

## 5. First deploy & verification

1. Deploy the scraper app; run the 02:00 command once manually from the Coolify
   task UI. Confirm logs show `[ok] <venue>: N events` lines and the task exits 0.
2. Deploy the web app; confirm the build log reads `DATABASE_URL` and produces
   `dist/`. Visit `https://cartelita.july.dev` — events should render.
3. Confirm Postgres has **no** public port mapping (`ss -tlnp` on the host shows
   it only on the internal Docker network / not on a public interface).

## Notes

- Python 3.14 is pinned in `scraper/Dockerfile` on purpose: the stdlib HTML parser
  parses some venue pages differently on 3.13 (far fewer events). Do not switch the
  scraper to Nixpacks (it caps at 3.13).
- Backups: enable Coolify's Postgres backup feature to object storage when ready.
````

- [ ] **Step 2: Verify the runbook covers every moving part**

Run: `grep -Eq "Base Directory.*scraper" docs/deploy.md && grep -Eq "0 2 \* \* \*" docs/deploy.md && grep -Eq "0 5 \* \* \*" docs/deploy.md && grep -q "cartelita.july.dev" docs/deploy.md && echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add docs/deploy.md
git commit -m "docs: Coolify deploy runbook

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Deploy on Coolify (manual, on the server)

**Files:** none (operator actions, performed in the Coolify UI / on the box)

This task is executed by the operator following `docs/deploy.md`. It cannot be run
from the dev sandbox (no Docker, no server access). Listed here so the plan's
definition of "done" includes a live, verified deploy.

- [ ] **Step 1:** DNS — point `cartelita.july.dev` at the Hetzner box.
- [ ] **Step 2:** Create the Postgres service (`docs/deploy.md` §1).
- [ ] **Step 3:** Create + deploy the scraper app from the Dockerfile (§2). Run the
      scrape command once manually; confirm `[ok]` lines and exit 0.
- [ ] **Step 4:** Create + deploy the web app via Nixpacks (§3); confirm `dist/`
      builds and `https://cartelita.july.dev` serves events.
- [ ] **Step 5:** Add the two Scheduled Tasks (§4); trigger each once to confirm.
- [ ] **Step 6:** Confirm Postgres is not publicly exposed (§5 step 3).

---

## Self-Review

- **Spec coverage:** topology (Tasks 1–4 + runbook), Docker/3.14 scraper (Task 1),
  Nixpacks web (runbook §3), `db.ts` env + SSL fix (Task 2), end-to-end build proof
  (Task 3), 02:00/05:00 scheduled tasks (runbook §4), internal-only Postgres
  (runbook §1/§5), domain `cartelita.july.dev` (runbook §3). The spec's reverted
  `requires-python` is already at `>=3.14` — no task needed.
- **Placeholders:** none — every file's full content is given; `<user>`/`<password>`/
  `<internal-host>` in the runbook are operator-supplied secrets by design, not plan gaps.
- **Consistency:** `cartelera` console script (pyproject) ↔ `CMD ["cartelera", ...]`
  ↔ scheduled command all match; `DATABASE_SSL` env introduced in Task 2 is referenced
  consistently in the runbook (left unset on internal net).
