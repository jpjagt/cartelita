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
   - `GITHUB_TOKEN=<fine-grained PAT>` and `GITHUB_REPOSITORY=jpjagt/cartelita` —
     scraper-health issues (see § 6). Without them, issue actions are only logged.
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

**Scrape (02:00).** Add a Coolify Scheduled Task (cron, server timezone) on the
scraper app:

| Schedule (cron) | App     | Command                                  |
|-----------------|---------|------------------------------------------|
| `0 2 * * *`     | scraper | `cartelera migrate && cartelera run all` |

- Runs `migrate` (idempotent) then `run all`. Each source gets a verdict
  (`[ok]`, `[DEGRADED]`, `[FAIL]`, `[SITE DOWN]` lines). Exit code is non-zero
  when any source is broken or site_down (its data was not written); degraded
  alone exits 0 — its data was written and its GitHub issue is the alert.

**Web redeploy (05:00).** The web app is a **static site**: Coolify serves the
prebuilt `dist/` from the deploy-time image via its proxy. There is no live web
container to run a command in, and rebuilding `dist/` in an ephemeral task
container would not change what the proxy serves. The **only** way to republish is
a real redeploy. Coolify also has **no** native scheduled-redeploy action — its
Scheduled Tasks just run a shell command in a throwaway container (coollabsio/
coolify discussions #2772, #4837; issue #8500).

So the redeploy is driven by a small always-on **`deploy/redeploy-cron`** Compose
service (Alpine + `crond`) that calls Coolify's deploy API on a schedule. A
redeploy re-runs `pnpm install` → `pnpm build` → `pnpm og` (per
`web/nixpacks.toml`) against the freshly-scraped DB. Deploy it as its own Coolify
app — see `deploy/redeploy-cron/README.md`. Default schedule `0 5 * * *` (an hour
after the scrape); set `CRON_SCHEDULE`, `COOLIFY_SERVER`, `COOLIFY_TOKEN`, and the
web app's `WEB_APP_UUID` in its env vars.

## 5. First deploy & verification

1. Deploy the scraper app; run the 02:00 command once manually from the Coolify
   task UI. Confirm logs show `[ok] <venue>: N events` lines and the task exits 0.
2. Deploy the web app; confirm the build log reads `DATABASE_URL` and produces
   `dist/` (e.g. `[build] N page(s) built`). Visit `https://cartelita.july.dev` —
   events should render.
3. Confirm Postgres has **no** public port mapping (`ss -tlnp` on the host shows
   it only on the internal Docker network, not on a public interface).

## 6. Scraper health (verdicts, hiding, GitHub issues)

Design: `docs/superpowers/specs/2026-10-12-scraper-health-design.md`. Every
`cartelera run` records a `scrape_run` per source with a verdict (healthy /
degraded / broken / site_down), hides upcoming events missing from 3 healthy
runs (reversible: `event.hidden_at`, nothing deleted), and opens / comments on /
closes one GitHub issue per bad source (labels `scraper-health`, `kind:<kind>`).
Commands: `cartelera health` (state of every source), `cartelera health
<source>` (detail, incl. venues degraded on their own), `cartelera health ack
<source>` (accept a legitimate change: the latest run becomes the new baseline —
older runs stop counting — the upcoming events it didn't see are hidden right
away — reversibly — and the issue closes), `cartelera health ack <source>
<venue>` (the same for one venue of a multi-venue source).

### Owner setup (one-off)

1. **Labels** on `jpjagt/cartelita`: create `scraper-health`, `kind:broken`,
   `kind:degraded`, `kind:site-down`, and `venue-review` (the rolling
   "`<source>`: venues to review" issue of an opt-out source, today
   jazzin.amsterdam — see its `_SOURCE.md`) (a token with only Issues access
   may not be able to auto-create labels).
2. **Issue token:** a fine-grained personal access token, repository access
   *only* `jpjagt/cartelita`, permission **Issues: Read and write** (nothing
   else). Set `GITHUB_TOKEN=<token>` and `GITHUB_REPOSITORY=jpjagt/cartelita` on
   the **scraper app** in Coolify (they're read at run time, so the scheduled
   task picks them up). Calendar-remind yourself of its expiry.
3. **Notifications:** watch the repo (at least Issues) so new issues email/push you.
4. **Claude repair agent** (`.github/workflows/claude.yml`, runs
   `anthropics/claude-code-action` when a comment mentions `@claude`):
   - install the Claude GitHub app on the repo: <https://github.com/apps/claude>
     (or run `/install-github-app` in Claude Code, which does this and the secret);
   - add the repository secret `ANTHROPIC_API_KEY` (Settings → Secrets and
     variables → Actions). To use a Claude subscription instead, set
     `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`) and swap the
     `anthropic_api_key` input for `claude_code_oauth_token` in the workflow.
   - Then on a health issue comment `@claude fix this`: it opens a PR; you
     review and merge; the normal deploy follows.

### Rollout of this feature (prod, once)

The jazzin.amsterdam scraper switches to a content-derived `external_id`, so
its first run re-keys every jazzin event; the old numeric-id rows must be
retired with `health rekey` (dry-run first).

1. Merge + deploy the scraper app (Coolify redeploys from `main`).
2. In the scraper app's terminal (or as a one-off task):
   ```sh
   cartelera migrate                                  # applies 0005_scraper_health.sql
   cartelera run jazzin-amsterdam                     # new keys; expect [ok] (first run: coverage skipped)
   cartelera health rekey jazzin-amsterdam            # dry-run: "would hide N ..."
   cartelera health rekey jazzin-amsterdam --apply    # hides legacy rows, acks the run
   cartelera health                                   # jazzin-amsterdam: healthy* (* = acked), streak 0
   ```
   If the 02:00 task already ran the new scraper, skip the `run`: `rekey` works
   off the latest jazzin run as long as it wrote content-keyed events.
3. Redeploy the web app (its queries now filter `hidden_at IS NULL`). Until
   `rekey --apply` has run, the DB holds old and new jazzin rows side by side,
   so do steps 2–3 together, before the next 05:00 web redeploy.

Other sources need nothing. Coverage is measured against what the previous
healthy (or acked) run saw, so each source's first run after the migration
skips it, and old rows that left the site long ago never count against
coverage: they are missed by every healthy run and hidden after the third.
The baseline rules apply from the third healthy run on.

### Rollout: jazzin.amsterdam opt-out venues (prod, once)

jazzin.amsterdam now creates venues it doesn't know at run time (see
`scraper/src/cartelera/scrapers/jazzin_amsterdam_SOURCE.md`). Create the
`venue-review` label first (above). Then merge + deploy the scraper app;
`cartelera run` applies `0006_discovered_venues.sql` itself (or run `cartelera
migrate`). The next jazzin run creates the ~10 venues it used to drop
(Frascati, ITA, Felix Meritis, …), lists them in its output, and opens the
"jazzin-amsterdam: venues to review" issue; the next web build shows them.
Review that issue: merge or deny names in `jazzin_amsterdam.py`, then close it.

## Notes

- Python 3.14 is pinned in `scraper/Dockerfile` on purpose: the stdlib HTML parser
  parses some venue pages differently on 3.13 (far fewer events). Do not switch the
  scraper to Nixpacks (it caps at 3.13).
- Backups: enable Coolify's Postgres backup feature to object storage when ready.
