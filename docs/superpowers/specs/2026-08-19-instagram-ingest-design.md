# Instagram ingest — design

Date: 2026-08-19. Supersedes §6 of
`docs/superpowers/specs/2026-08-18-multi-city-yerevan-design.md` (that section
was a sketch; this is the design). Venue research: `docs/yerevan.md`.

## Goal

A generic engine that turns a public Instagram profile into an ordinary
Cartelita source: Playwright captures posts, a provider-independent vision LLM
extracts events from caption + flyer images, and everything downstream sees
ordinary `ScrapedEvent`s. Applied first to the two Yerevan venues that are
blocked without it (Cinema House, Mezzo), built to serve future IG-only venues
in any city.

## Decisions (settled in discussion)

- **Playwright is the engine.** No paid scraper APIs (Apify et al.). The DM
  intake idea (poll our own professional account's inbox via the official
  Conversations API — feasible, Standard Access, no app review, but shares
  arrive as bare media URLs without caption/shortcode) is a **wholly separate
  future design**, not part of this subsystem.
- Runs on **Coolify** with the nightly scrape; all IG traffic exits through a
  **pay-as-you-go residential proxy** (~$2–5/month at our volume). No
  local-machine cron.
- Logs in as a **dedicated scrape account** — warmed up manually, used only by
  the poller, never the Cartelita brand handle. A ban costs setup time only.
- Extraction is **trust-the-model, spot-check**: structured output with a
  per-event confidence, threshold-filtered, reviewed via run logs. No evidence
  quoting, no human review queue.
- Raw posts and extractions live in **Postgres** — capture and parse each post
  **once**; a prompt-version bump does **not** re-extract already-parsed posts
  in production (re-extraction is a manual/dev action).
- An IG profile is a **source**, and like any source may feed **multiple
  venues**; the extractor attributes each event to a venue.
- The vision model is **provider-independent** (config string via litellm),
  never hardcoded.
- No machine translation — but a post may itself contain an event in several
  languages, and the extractor may return those as translations.

## 1. Shape: a module, not a service

`scraper/src/cartelera/ig/` inside the existing scraper — no separate
deployment:

- `capture.py` — Playwright session, profile polling, image download.
- `archive.py` — the Postgres raw-post store.
- `extract.py` — vision-LLM extraction with the cache check.
- `source.py` — glue: archive → publish gate → `ScrapedEvent`s, plus an
  `IgSourceConfig` the thin per-source scrapers are built from.

Per-source IG scrapers stay thin: handle, venue roster with per-venue category
lists and prompt hints. A 1:1 profile uses `register(...)`; a profile covering
several venues (a promoter account, a portal like rocker.am) uses
`register_source(...)` and the roster is its editorial whitelist, exactly like
any aggregator. IG sources run inside the normal nightly `cartelera run`.

## 2. Capture (Playwright)

- Chromium via Playwright (already in the stack), headless, stealth launch
  args, proxied through `IG_PROXY_URL`.
- The login session (`storage_state` JSON) is persisted in Postgres and
  reused; login (`IG_USERNAME`/`IG_PASSWORD`) runs only when the session is
  invalid. A login failure or checkpoint marks the source **failed** (existing
  staleness machinery) and stops — no aggressive retries; posts don't vanish,
  the next night can catch up.
- Per profile: open the profile page and **intercept the timeline XHR JSON**
  (shortcode, caption, timestamp, all carousel image URLs) rather than
  DOM-scraping; download **all** images of each post through the same
  session/proxy. Fetch the last ~12 posts, stopping early at shortcodes
  already archived. Sequential profiles, jittered delays, nightly — shaped
  like a person.
- Pinned posts are captured like any other; **stories are out of scope**
  (ephemeral, different surface, different risk).

## 3. Archive (Postgres, one additive migration)

- `ig_post`: `shortcode TEXT PK`, `source_slug TEXT`, `handle TEXT`,
  `caption TEXT`, `posted_at TIMESTAMPTZ`, `captured_at TIMESTAMPTZ`, plus
  extraction columns `extraction JSONB NULL`, `model_id TEXT NULL`,
  `prompt_version INT NULL`, `extracted_at TIMESTAMPTZ NULL`.
- `ig_post_image`: `shortcode FK`, `idx INT`, `content_type TEXT`,
  `bytes BYTEA` — volume is trivial at this venue count.
- `ig_session`: single-row `storage_state JSONB`, `updated_at`.
- Capture upserts raw posts; nothing ever re-touches Instagram for a post we
  already hold. A banned account loses future capture, never history.

## 4. Extraction (provider-independent vision LLM)

- **litellm** is the provider abstraction; the model is the config string
  `IG_EXTRACT_MODEL` (e.g. `gemini/gemini-2.5-flash`,
  `anthropic/claude-haiku-…`). Chosen over a hand-rolled adapter because we'd
  otherwise reimplement its per-provider image-encoding matrix.
- Runs only where `extraction IS NULL` — **one parse per post, ever**, in
  production. `prompt_version` is recorded for provenance; bumping it does not
  trigger re-extraction (a manual/dev flag can force it for selected posts).
- Input: the caption plus **all** archived images of the post, and the
  source's venue roster (slug, name, allowed categories, hints).
- Output (JSON schema-forced): a **list** of candidate events — a weekly
  line-up post is one post, many events — each with:
  - the `ScrapedEvent`-shaped fields (title, date, time, description, price);
  - `venue_slug` chosen from the roster (implicit for 1:1 sources);
  - `category` chosen from that venue's allowed categories — Mezzo
    (jazz + classical + blues/rock/folk) needs this on day one;
  - `contents`: one or more `{lang, title, description}` variants when the
    post itself carries the event in several languages (e.g. hy then en in
    one caption). This is extraction of what the post says, not machine
    translation. **Rollback valve:** if multi-language output confuses the
    model in practice, flatten the contract to a single `{lang, …}` per
    event;
  - `language` (the *performance* language, display-only free text) only when
    the post states it — unrelated to `contents.lang`;
  - a single `confidence` float.
- **Publish gate:** an event needs a fully resolvable date (year inferred as
  nearest-future within 6 months) **and** `confidence ≥ 0.75`
  (`IG_CONFIDENCE_THRESHOLD`). Anything below is dropped and logged — silence
  over noise. Publishes and drops both appear in the run log for spot-checks.
- Cost at our volume (≤10 new posts/night, flash-tier model, even with
  10-image carousels): cents per month. The once-per-post cache is the cost
  ceiling.

## 5. Emission

`source.py` reads the archive each night and emits, from **all** extracted
posts (not just tonight's), every gated event with `start_date >= today` —
the cache makes this free and keeps upserts fresh. Mapping:

- canonical content = the `contents` variant in the city's default locale if
  present, else the first variant; remaining variants become
  `ScrapedTranslation`s (→ `EventTranslation`).
- `external_id = ig-{shortcode}` (`-{n}` for multi-event posts) — the
  existing dedup tiers work unchanged.
- `source_url = https://www.instagram.com/p/{shortcode}/`;
  `image_url` = the post's first image (served via IG's CDN URL captured at
  scrape time; if those links rot, revisit serving from the archive — out of
  scope now).
- An event attributed to a venue outside the roster is dropped and logged
  (whitelist semantics, same as aggregators).

## 6. Recon ladder (skill update, not code)

`writing-a-scraper` Phase 1 gains a step: when a venue looks IG-only, exhaust
the easier surfaces **in order** before writing an IG source — esora's source
list → link-in-bio services (Linktree etc.) → the Facebook page →
tomsarkgh/ticket-am/eventix → Google Maps business posts. IG capture is the
floor, not the default.

## 7. Tier (a) dissolves into ordinary scrapers

Pantomime Theatre (`17432552-b94e-41c7-8401-855e688d6a62`) and Mihr
(`82d1073c-6107-4dfd-b14e-533c0bcd29c9`) get trivial esora-feed scrapers now,
on the Malkhas pattern. Dormant feeds emit 0 events, which is harmless — and
the nightly run *is* the re-check: when esora repopulates them, events appear
with no monitoring subsystem at all. Not part of IG ingest.

## 8. First wave

IG sources for **Cinema House** (`@cinemahouse.evn`, film) and **Mezzo**
(jazz/classical/…) only — two profiles with different post styles is enough to
prove the engine and tune the prompt. Tonelab, Hayfilm (which may only need
its live esora source), Karin, rocker.am and any Barcelona IG-only venues wait
until the engine has survived a few weeks.

## 9. Testing

- Capture: parse saved timeline-XHR fixtures (shortcodes, captions, carousel
  URLs); session-restore and stop-at-seen logic unit-tested.
- Extraction: fixture posts (caption + flyer images, Armenian/Russian among
  them, incl. one multi-event line-up and one multi-language caption) with
  expected outputs asserted structurally — dates exact, gate honored,
  venue/category from roster. LLM calls mocked at the litellm boundary; one
  optional live smoke test behind an env flag.
- Emission: archive → `ScrapedEvent` mapping incl. translations and
  `external_id` stability.
- Live verification of the first two sources per the writing-a-scraper skill,
  with `SOURCE.md` files recording where each field comes from.

## Out of scope

DM intake (separate future design), stories, a human review queue, automatic
re-extraction on prompt bumps, machine translation, serving flyer images from
our archive, and any IG interaction beyond reading profiles (no likes,
follows, or comments from the scrape account by the poller).
