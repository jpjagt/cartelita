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
   - (Do NOT set `DATABASE_SSL`; the internal network is plain TCP. Set
     `DATABASE_SSL=require` only if the DB is ever reached over a public, TLS port.)
5. Domain: `cartelita.july.dev` (Coolify provisions TLS via Let's Encrypt).
   Point the `cartelita` DNS record at the Hetzner box first.

## 4. Scheduled tasks

In Coolify, add two Scheduled Tasks (cron, server timezone):

| Schedule (cron) | App     | Command                                  |
|-----------------|---------|------------------------------------------|
| `0 2 * * *`     | scraper | `cartelera migrate && cartelera run all` |
| `0 5 * * *`     | web     | redeploy (trigger a rebuild)             |

- The 02:00 scraper task runs `migrate` (idempotent) then `run all`. Its exit
  code is non-zero if any venue failed — check the task logs.
- The 05:00 web task triggers a redeploy so Astro rebuilds the static site from
  the freshly-scraped DB. If Coolify's scheduled task can't trigger a redeploy
  directly, use the web app's **deploy webhook**: `curl -fsS <deploy-webhook-url>`.

## 5. First deploy & verification

1. Deploy the scraper app; run the 02:00 command once manually from the Coolify
   task UI. Confirm logs show `[ok] <venue>: N events` lines and the task exits 0.
2. Deploy the web app; confirm the build log reads `DATABASE_URL` and produces
   `dist/` (e.g. `[build] N page(s) built`). Visit `https://cartelita.july.dev` —
   events should render.
3. Confirm Postgres has **no** public port mapping (`ss -tlnp` on the host shows
   it only on the internal Docker network, not on a public interface).

## Notes

- Python 3.14 is pinned in `scraper/Dockerfile` on purpose: the stdlib HTML parser
  parses some venue pages differently on 3.13 (far fewer events). Do not switch the
  scraper to Nixpacks (it caps at 3.13).
- Backups: enable Coolify's Postgres backup feature to object storage when ready.
