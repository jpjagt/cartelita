# Cinema House — source map

Կինոյի տուն, the Union of Film Professionals of Armenia's own house at 18/1
Vardanants St, Yerevan: three halls (500/120/80 seats, renovated 2018),
retrospectives, archival and restored programmes, director Q&As, and festival
hosting (Golden Apricot every July). The Filmoteca analogue for Yerevan.

**Source type: Instagram ingest** (`cartelera/ig`), handle `@cinemahouse.evn`.
Not a scraper of a website — there is no website, and no listing service
carries the programme (ladder below).

## Recon ladder (writing-a-scraper Phase 1, IG-only branch)

Checked **2026-08-19** (rungs 1 and 4 re-checked live today; the rest carried
over from the 2026-08-18 Yerevan recon in `docs/yerevan.md`):

| # | Rung | Result |
|---|---|---|
| 1 | **esora.app** | Source **exists**: `eventSourceId=7eb1e6d4-6e58-49a3-befe-636fd82e596d`, name "Cinema House", `instagramUsername: "cinemahouse.evn"`, `eventCount: 17`. But `GET /api/events/feed?eventSourceId=7eb1e6d4-…` returns `pagination.total: 0` — **zero upcoming occurrences**; esora ingests the same IG account and is currently behind. Re-check periodically: if this feed repopulates, an esora scraper (see `scrapers/esora.py`) is strictly cheaper than IG capture and should replace this source. |
| 2 | **Link-in-bio** | Not checkable without reading the IG bio, which needs the very capture path this source implements. Re-check by hand once credentials exist. |
| 3 | **Facebook** | The venue's programme is posted to `facebook.com/armenianunionoffilmprofessionals` (per the European Film Academy's venue page) plus a FB group. Login-walled to plain HTTP (a fetch of a page returns the app shell, no event data). No public dated listing. |
| 4 | **Ticketing/aggregators** | tomsarkgh.am has a venue page (`/hy/venue/2577/Կինոյի-տուն.html`) that lists **no** Cinema House events — the only event links on it are the site-wide "popular events" sidebar (Tata Simonyan, Coca-Cola Fest…). Nothing on ticket-am.com, toms.am or eventix.am (2026-08-18). |
| 5 | **Google Maps posts** | Not reachable from this environment (no Maps API key, browser recon unavailable per the skill's Phase 1 caveat). |
| 6 | **IG ingest** | Chosen — the floor of the ladder, because everything above is genuinely empty. |

Also confirmed dead: no official site. `unikino.am` and `uca.am` do not
resolve (the 2GIS listing still prints `www.uca.am` as the union's site; it is
not live), so `site_url = None`.

## Handle verification

`@cinemahouse.evn` — from the spec (§8), and independently corroborated
**without touching instagram.com**: esora.app's public event-source record for
"Cinema House" (`https://esora.app/api/event-sources?city=yerevan&limit=2000`)
carries `instagramUsername: "cinemahouse.evn"` alongside a description naming
"the Union of Film Professionals of Armenia (Cinema House)". Address
(18/1 Vardanants St) from 2GIS (`2gis.am/yerevan/firm/70000001087002432`,
"Կինոյի տուն, Հայաստանի կինոգործիչների միություն, Վարդանանց փողոց, 18/1") and
Spyur (`spyur.am/en/companies/house-of-cinematographers/3807/`, "Yerevan
Vardanants St., 18 Building").

## Where each field comes from

There are no CSS selectors here: every field is produced by the ingest engine
— a vision LLM reads the post's **caption and every flyer image** once
(`ig/extract.py`, `PROMPT_VERSION`), the result is stored verbatim in
`ig_post.extraction`, and `ig/source.py` maps what tonight's gate keeps.

| field | from |
|---|---|
| `title` / `description` | the extracted `contents` entry whose `lang` is `hy` (the source's `canonical_lang`), else the first entry. Extraction, never translation: only languages the post itself is written in appear. |
| `translations` | the remaining `contents` entries (first entry per language), each with the post URL as `source_url` |
| `start_date` | gate-resolved from the stated `day`/`month`/`year`. An unstated year is inferred as the nearest future one; an unresolvable date drops the event (`gate_events`) |
| `start_time` / `start_times` | extracted `time` ("HH:MM"), `None` when the post states none |
| `price` | extracted `price`, free text exactly as posted ("free", "2000֏"); `None` when unstated — never inferred |
| `language` | the **screening** language, only when the post states it (dubbed/subtitled notes) |
| `category_slugs` | `[category]`, which the model must choose from this venue's list — `film` is the only allowed value. Anything else is dropped and logged by `source.py` (never allowed to reach the upsert's fail-fast) |
| `venue_slug` | the extracted `venue_slug`; single-venue source, so `None` is fine and off-roster values are dropped and logged |
| `image_url` | the first archived image of the post (`ig_post_image.idx = 0`), an Instagram CDN URL captured at scrape time |
| `source_url` | `https://www.instagram.com/p/{shortcode}/` |
| `external_id` | `ig-{shortcode}`, or `ig-{shortcode}-{index}` when the post announced several events — `index` is the event's position in the **stored** extraction, which is frozen at parse time (the post-gate order shifts as dates pass) |
| `annotations` | none: the extraction schema has no tag field |
| `recurrence_hint` | none |

**Publish gate** (`extract.gate_events`, re-run every night over every stored
extraction): `confidence >= IG_CONFIDENCE_THRESHOLD` (default 0.75), a
resolvable date, and that date inside `[today, today+6 months]` with today
taken in `Asia/Yerevan`. Every drop is logged at INFO.

**Prompt hints** (`cinema_house.py: HINTS`) tell the model this is a
cinematheque, that captions/flyers are Armenian first (sometimes ru/en), that
the flyer carries title + date + time, that a retrospective flyer may list
several dated screenings (one event per screening), and that Golden Apricot
programming runs through the same account in July.

## Live verification: **PENDING** ⚠️

This source has **never been run against Instagram.** It cannot be: capture
needs the scrape account's session plus the residential proxy, and neither
exists in this environment (no credentials, `ig_session` empty). Every claim
above about the *engine* is covered by tests (`tests/test_ig_source.py`,
`test_ig_capture.py`, `test_ig_extract.py`); every claim about **what this
profile actually posts** is unverified.

Once the account and `IG_PROXY_URL` exist, verify like this:

```bash
cd scraper
uv run cartelera ig-login          # once: human logs in, storage_state -> Postgres
uv run cartelera dry-run cinema_house
```

Unlike an ordinary scraper's, this `dry-run` **does** touch Postgres
(`DATABASE_URL`, migrations applied): the archive is where captured posts and
their extractions live. It writes to `ig_post`/`ig_post_image` but never to
`event` — no upsert, no seed.

`dry-run` prints:

```
[dry-run] cinema-house: N events
  with start_time:  n/N (x%)
  with price:       n/N (x%)
  with image_url:   n/N (x%)
  with annotations: 0/N (0%)
  with external_id: N/N (100%)
  categories:       {'film': N}
  --- first 5 events ---
  YYYY-MM-DD HH:MM |    price | title
```

Then do the field-by-field cross-check the skill demands, against an
INDEPENDENT read of the profile (open the actual posts by hand and compare
title / date / time / price / language for the first ~6 events). Expected
shape: `image_url` 100% (every post has a flyer), `annotations` 0%,
`categories` `{'film': N}` only, no duplicate `external_id`s. Watch
especially for:

- **Dates without a year** on flyers — check the inferred year is right.
- **Multi-screening retrospective flyers** — every date must produce its own
  event, or occurrences collapse.
- **Non-event posts** (obituaries, greetings, festival recaps) must yield zero
  events, not a hallucinated one.

Record the result here as "Last verified: YYYY-MM-DD via …" and re-tune
`HINTS` from what you see; the extraction is cached per post, so tuning hints
only affects posts captured afterwards.

Last verified: **never** (blocked on IG credentials, 2026-08-19).
