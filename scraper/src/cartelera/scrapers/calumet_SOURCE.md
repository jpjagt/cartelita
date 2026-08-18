# Calumet Ethnic Lounge Bar — source map

Small live-music/DJ bar on Pushkin St, Yerevan (56-a Pushkin St), same street
as Malkhas. World/ethnic-lounge branding, live bands + weekly DJ nights, very
local crowd.

## Why Esora, not the venue's own site

- No official website resolves (`calumet.am`, `calumetlounge.am` — DNS
  failure). The bar's only channel is Instagram (`instagram.com/calumetyerevan`,
  verified 200 via HTTP HEAD, 2026-08-18).
- `tomsarkgh.am` has no Calumet listing — a site search for "calumet" returns
  zero results (only the search-page's own language-switcher links echo the
  query string back).
- **esora.app** runs a dedicated Calumet source page, fed from the bar's
  Instagram posts: `eventSourceId = 0d96db49-9628-4868-9c23-f283ebc86463`
  (found via `GET https://esora.app/api/event-sources?city=yerevan&limit=500`,
  matching `"name": "Calumet Ethnic Lounge Bar"`, `instagramUsername:
  "calumetyerevan"`, `eventCount: 38`). Same public JSON API pattern as
  Malkhas (`scraper/src/cartelera/scrapers/malkhas_jazz_club.py`). Not a STOP
  case — events are on esora's structured feed, not Instagram-only.

## Data source: Esora's public JSON API

```
GET https://esora.app/api/events/feed?eventSourceId=0d96db49-9628-4868-9c23-f283ebc86463&limit=100&page=N
```

Same shape as Malkhas's feed (`result.eventOccurrenceIds` /
`entities.{eventOccurrences,events}`). One quirk found here: the
**un-parameterized feed only returns occurrences `today`-or-later** — on the
recon date (2026-08-18) that was a single event, because Calumet's Instagram
(and hence Esora) only has one date confirmed ahead at a time. Adding
`&from=YYYY-MM-DD` returns the full history regardless of `today`
(`limit` is capped at 100 server-side — `>100` 400s with a `VALIDATION_ERROR`).
Used `from=2025-01-01` during recon to pull the full history (66 occurrences /
38 events, 2025-11-11 → 2026-08-18) for category-mix analysis and as the test
fixture; the scraper itself calls the plain (`from`-less) feed URL, exactly
like Malkhas, and relies on Esora's own "today-or-later" default plus the
parser's defensive `today`-or-later filter.

## Category: real discriminator, not the initially-hypothesized folk+jazz

The task brief hypothesized `["folk", "jazz"]` (world/ethno/folk/jazz) from
editorial vibes. Checked against the actual programme (all 66 historical
occurrences, `entities.events[].category` + full-text search of every
title/description):

- **`jazz` appears zero times anywhere in the data.** Not a single event
  mentions jazz.
- Esora's own `category` field on each event is a clean, real, two-value-ish
  discriminator: `clubbing` (16/38 unique events: B2B/DJ sets — "Electro
  Almaza Tuesdays", "Calcoolsun B2B Series", birthday DJ sets) vs
  `live_music` (18/38: live bands/acoustic sets — mixed rock, folk, blues,
  and unlabeled "vibes" sets) vs `music`/`social` (4/38 combined: an acoustic
  folk night booked under `music`, plus two DJ-flavored bar parties and one
  anniversary party booked under `social`).
- Within `live_music`, real sub-genre signal is present in a minority of
  events (`tags: ["rock"]` on the FIX/Tatka Trio entries; "Armenian folk
  evening" / "Armenian folk music" in the description of the one recurring
  acoustic act) but most events carry only the placeholder tag
  `live_music_other` — not a reliable jazz/folk/rock split at the tag level.

Chosen mapping — Esora's `category` field is the discriminator:
`clubbing` → **`club`**; everything else (`live_music`, `music`, `social`) →
**`folk`** (the bar's live-band/in-house-night bucket; closest existing
category to "world/ethnic live bands", and matches the venue's own
`live_music` labeling far better than `jazz` would). `category_slugs =
["club", "folk"]` on the venue, each in its own whitelisted list
(`ListMembership(list_slug="club", whitelist_category_slug="club")` /
same for `folk`) — the same multi-category pattern as Jamboree
(`jazz`+`club`).

Real per-event tags that survive (`rock` mainly) go to `annotations`, minus
Esora's placeholder `*_other` tags (`live_music_other`, `clubbing_other` —
these mean "no real tag", not information).

## Field mapping

| field | from |
|---|---|
| title / description | `i18n.*.hy.content` (canonical = Yerevan default locale), fallback to the event's base `title`/`description` (a few just-ingested events have empty `i18n` — not yet machine-translated) |
| translations | `i18n.*.{ru,en}.content`, source_url `https://esora.app/{ru,en}/yerevan/events/{eventId}` |
| source_url | `https://esora.app/hy/yerevan/events/{eventId}` (the IG `detailUrl` is per-event here, unlike Malkhas, but the Esora page is still the more stable canonical URL) |
| start_date / start_time | occurrence `startDate` / `startTime` (ISO, Asia/Yerevan wall clock) |
| price | occurrence `price` — **real free text on this venue** (unlike Malkhas, which is always null): `"No entrance fee"` / `"Free"` / `"free entrance"` / `"entrance is free"` variants → `"free"`; a minor AMD range (`hi < 2× lo`, e.g. `"5000–7000 AMD"`) collapses to the high value (`"7000 AMD"`) per the price-range rule; anything else passes through verbatim (`"3000 AMD"`, `"Tickets at the bar"`); `null` → `None` |
| category | `event.category`: `"clubbing"` → `club`; else → `folk` (see above) |
| annotations | `event.tags` minus Esora's placeholder `*_other` tags |
| language | `None` (never stated) |
| image_url | `https://esora.app/img/unsafe/1200x0/filters:no_upscale():format(jpeg)/events/{eventId}/{media[0].localFileName}` (first non-disabled image); verified 200 via HTTP fetch |
| external_id | `esora-occ-{eventOccurrenceId}` — per-occurrence UUID; several nights (e.g. "Electro Almaza Tuesdays", "Cheyenne", "Sasha Lenivec") recur under the same event page, so the event id alone would collapse occurrences |

Occurrences/events with `disabledAt`, and occurrences dated before `today`
(Asia/Yerevan), are skipped.

## Quirks

- The un-parameterized feed's "today-or-later" horizon is genuinely short
  (often one confirmed date) — Calumet posts to Instagram roughly weekly, so
  the live run will typically yield very few (sometimes just one) upcoming
  event at any given time. This is real data sparsity, not a scraper bug;
  Malkhas by contrast always has ~6 (a full week) because it posts its whole
  week's line-up at once.
- Same weekly-repost titling quirk as Malkhas is absent here — Calumet's
  events are individually captioned per date, so `title` is usually specific
  (an artist/DJ name), not a repeated week label.
- If the Calumet source page ever 404s or `eventCount` drops to 0, the bar
  may have moved off Instagram/Esora — re-recon (`eventSourceId` is the
  stable key: `0d96db49-9628-4868-9c23-f283ebc86463`).

Last verified: 2026-08-18, verified via HTTP fetch (browser unavailable —
browser-use wanted to attach to the user's real Chrome, so per policy we used
httpx instead). See scraper output vs. live API cross-check below.
