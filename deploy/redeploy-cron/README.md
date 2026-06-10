# redeploy-cron

An always-on Alpine + `crond` container that calls Coolify's deploy API on a
schedule to **redeploy the web app**. This is how Cartelera reschedules the
static-site rebuild after the nightly scrape, because Coolify has no native
scheduled-redeploy action and its Scheduled Tasks run in throwaway containers
that can't republish a static site. See `docs/deploy.md` §4.

## Deploy on Coolify

1. New **Application** from this repo.
2. Build Pack: **Docker Compose**. **Base Directory:** `deploy/redeploy-cron`.
3. Environment Variables (see `.env.example`):
   - `COOLIFY_SERVER` — Coolify host, no scheme (e.g. `coolify.july.dev`)
   - `COOLIFY_TOKEN` — Coolify API token **with deploy permission**
     (Settings → Keys & Tokens → API tokens)
   - `WEB_APP_UUID` — the **web app's** UUID, found on that app's
     Webhooks page (the `uuid=` in its API deploy URL)
   - `CRON_SCHEDULE` — 5-field cron in the **server timezone**
     (default `0 5 * * *` = 05:00, an hour after the 02:00 scrape)
4. If you enabled Coolify's **API allow-list**, add this server's IP.
5. Deploy. The boot log prints the installed crontab; on each tick it logs
   `[CRON] redeploy triggered at <utc>`.

## Verify

After deploy, force one tick to confirm the token/UUID work:

```sh
curl -fsS -X POST -H "Authorization: Bearer $COOLIFY_TOKEN" \
  "https://$COOLIFY_SERVER/api/v1/deploy?uuid=$WEB_APP_UUID&force=true"
```

A `200` with a deployment payload means it's wired correctly; watch the web
app's Deployments tab for the triggered build.
