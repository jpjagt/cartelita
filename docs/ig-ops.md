# IG ingest — go-live runbook

Operational checklist for turning on Instagram ingest (`scraper/src/cartelera/ig/`,
design: `docs/superpowers/specs/2026-08-19-instagram-ingest-design.md`) in
production. Do these once, in order, before the first live `cartelera run all`
that includes `cinema-house` or `mezzo`.

## 1. Create and warm the dedicated scrape account

- Create a fresh Instagram account used **only** by the poller — never the
  Cartelita brand handle, never a personal account. A ban costs setup time
  only if it's isolated.
- Follow the target venues (`@cinemahouse.evn`, `@mezzoclub`).
- Browse normally for **1–2 weeks** before turning on nightly capture: like a
  few posts, scroll the feed, view some stories. A brand-new account that
  immediately starts polling profiles on a schedule is exactly the pattern
  Instagram's abuse detection looks for.

## 2. Provision the residential proxy

- Get a pay-as-you-go residential proxy (~$2–5/month at this volume).
- Set `IG_PROXY_URL` (`scheme://user:pass@host:port`) everywhere IG code runs:
  - the scraper's Coolify environment (nightly `cartelera run all`);
  - wherever you run `cartelera ig-login` from (step 4) — **the same proxy**,
    so the session is minted from the same exit IP the nightly capture uses.
- Unset = direct connection. Fine for local dev against fixtures, never for
  anything that touches real Instagram.

## 3. Configure extraction

- `IG_EXTRACT_MODEL` — a litellm model string. Defaults to
  `gemini/gemini-2.5-flash` if unset.
- The provider's API key, read by litellm itself (not by us): `GEMINI_API_KEY`
  for the default model, `ANTHROPIC_API_KEY` for `anthropic/*`, etc. There is
  no cartelera-side config for this key — set it in the same env as
  `IG_EXTRACT_MODEL`.
- `IG_CONFIDENCE_THRESHOLD` — optional, defaults to `0.75`. Leave it unset
  until step 5's spot-check gives a reason to move it.

## 4. Run `cartelera ig-login` once

Run this **once**, from any machine with a display (it opens a *headed*
browser — there is no headless/automated login):

```
IG_PROXY_URL=... DATABASE_URL=<production DATABASE_URL> uv run cartelera ig-login
```

- Route it through the **same `IG_PROXY_URL`** as production capture (step 2).
- Point `DATABASE_URL` at the **production** database — the session is stored
  in Postgres (`ig_session`, single row) and that's the row the nightly job
  reads.
- A human completes the login and any checkpoint/2FA prompt in the opened
  browser window; the command waits (10 minutes) for the `sessionid` cookie to
  appear, then saves `storage_state` and exits.
- This is deliberate, not a missing feature: there is no `IG_USERNAME`/
  `IG_PASSWORD` automated login path (see the spec's "As built" section) —
  checkpoints and 2FA are exactly what an automated login fails at, and a
  human clears them in seconds.
- The nightly capture re-persists a refreshed session after every successful
  run, so this is a true one-time bootstrap, not a recurring chore — re-run it
  only if capture starts failing with "run `cartelera ig-login`" in the logs
  (session went invalid: logout, password change, or a ban).

## 5. First live run checklist

Do these **in order**, after step 4:

1. **Eyeball the handle before/at login.** While logged in as the scrape
   account, open `instagram.com/mezzoclub` by hand and confirm it's actually
   Mezzo Classic House Club (28 Isahakyan St, Yerevan; nightly line-up posts)
   before trusting a capture — see `scraper/src/cartelera/scrapers/mezzo_SOURCE.md`
   for why this handle needed extra verification (it was established from
   non-Instagram evidence, not a live fetch).
2. **Dry-run each source, one at a time:**
   ```
   cd scraper
   uv run cartelera dry-run cinema_house
   uv run cartelera dry-run mezzo
   ```
   `dry-run` skips seed/upsert but is **not** DB-free for an IG source — it
   still reads/writes `ig_post`/`ig_session` via the real production
   `DATABASE_URL`, and performs a real capture + extraction call. Run it with
   the same `IG_PROXY_URL`/`IG_EXTRACT_MODEL`/API key as production.
3. **Dump one raw timeline response and diff its shape against the test
   fixture.** Instagram's timeline JSON shape can drift without warning, and
   a parse drift surfaces as an **empty capture** (no error, no crash) — see
   `scraper/tests/test_ig_capture.py`'s fixture builders for the shape the
   parser expects (`TIMELINE_CONNECTION_KEY`, `edges[].node.code/caption/
   taken_at/image_versions2`). If a dry-run above reports 0 events where you
   expect some, this is the first thing to check.
4. **Spot-check the extracted events** in the dry-run output (or query
   `ig_post.extraction` directly) against what the post/flyer actually says.
   Tune the venue's `HINTS` in `scraper/src/cartelera/scrapers/{cinema_house,mezzo}.py`
   and/or `IG_CONFIDENCE_THRESHOLD` based on what you see — too many
   low-confidence drops means the hints need work; a wrong category or date
   means the model needs a clearer nudge.

## Staleness signal until step 4 is done

**Until `cartelera ig-login` has been run**, nightly `cartelera run all` will
report `cinema-house` and `mezzo` as `[FAIL]` (no stored Instagram session).
**This is the intended staleness signal, not a bug** — it's the same
mechanism that flags any other source failure, and it's exactly what should
happen for a source that can't run yet. Don't "fix" it by faking a session;
run step 4.

## Escape hatch: a permanently-unparseable post

A post is parsed **at most once** in production — there is no `cartelera`
flag to force re-extraction (see the spec's "As built" section). If a post is
stuck in a bad state (e.g. it will never be a real event, or the model keeps
failing on it and it's clogging the run log every night), mark it parsed with
no events directly in Postgres:

```sql
UPDATE ig_post
SET extraction = '{"events": []}'::jsonb,
    model_id = 'manual',
    prompt_version = 0,
    extracted_at = now()
WHERE shortcode = '<shortcode>';
```

This satisfies `posts_missing_extraction`'s `extraction IS NULL` filter (the
post stops being retried) while `gate_events` sees an empty `events` list and
emits nothing for it. `prompt_version = 0` marks it as not having gone through
a real prompt run (real versions start at 1); `model_id = 'manual'` marks it
as a human decision, not a model one. Verify column semantics against
`scraper/migrations/0005_ig_ingest.sql` before reusing this pattern elsewhere.
