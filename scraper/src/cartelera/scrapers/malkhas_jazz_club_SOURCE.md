# Malkhas Jazz Club — source map

Yerevan's iconic jazz club (Levon Malkhasyan's), 52/1 Pushkin St. Live jazz
seven nights a week from ~21:00.

## Why Esora, not the venue's own site

- `malkhas.am` (and www/http variants) does not resolve — the club has **no
  official website** (2026-08-18). Its own channels are Facebook
  (`facebook.com/MalkhasClub`) and Instagram (`instagram.com/malkhasclub`),
  neither scrapeable.
- `tomsarkgh.am` has a Malkhas venue page (`/en/venue/40/...`) but it lists no
  upcoming Malkhas events — only a generic "popular events" sidebar for other
  venues (Malkhas shows there are not ticketed; past one-off concerts only).
- **esora.app** runs a dedicated Malkhas source page
  (`https://esora.app/en/yerevan/sources/2f85265c-78f0-4a7c-9580-43163182c3cf`)
  fed from the club's weekly Instagram line-up posts, with one dated occurrence
  per night (artist name, date, 21:00). This is the only per-date listing that
  exists anywhere; chosen.

## Data source: Esora's public JSON API

```
GET https://esora.app/api/events/feed?eventSourceId=2f85265c-78f0-4a7c-9580-43163182c3cf&limit=100&page=N
```

(The source page server-renders the same Redux state; the API is what the page
itself calls — found via `serializeEventsFeedQuery` / `url:/events/feed?...` in
Esora's JS chunks. No auth needed.)

Response shape:

- `result.eventOccurrenceIds` — ordered occurrence ids; `result.pagination`
  (`page`/`totalPages`) — currently 1 page (~6 events = the current week's
  line-up; Esora ingests the club's weekly IG post, so the horizon is short).
- `entities.eventOccurrences[id]` — `startDate` ("2026-08-18"), `startTime`
  ("21:00:00"), `endDate`/`endTime` (null), `price` (**always null** — Malkhas
  does not publish a cover charge; the club takes phone reservations), `eventId`,
  `disabledAt`.
- `entities.events[eventId]` — `title` (artist name), `description`,
  `i18n.title/description.{en,hy,ru}.content` (Esora's own per-locale display
  content, scraped as-is; we do not translate), `category` ("live_music"),
  `tags` (["jazz"]), `media[].localFileName`, `detailUrl` (the Instagram post —
  same URL for the whole week, NOT usable as source_url), `disabledAt`,
  `visibility`.

## Field mapping

| field | from |
|---|---|
| title / description | `i18n.*.hy.content` (canonical = Yerevan default locale), fallback to the event's base `title`/`description` |
| translations | `i18n.*.{ru,en}.content`, source_url `https://esora.app/{ru,en}/yerevan/events/{eventId}` |
| source_url | `https://esora.app/hy/yerevan/events/{eventId}` (per-event Esora page; the IG `detailUrl` is shared by all events, would collapse upsert tier 2) |
| start_date / start_time | occurrence `startDate` / `startTime` (ISO, Asia/Yerevan wall clock) |
| price | occurrence `price` (null today → `None`; number would render as "N AMD") |
| category | fixed `jazz` — the venue programs only live jazz (feed: `category=live_music`, `tags=["jazz"]`) |
| annotations | feed `tags` minus `jazz` (the discriminator/category never leaks in) |
| language | `None` (never stated; artist-name titles only) |
| image_url | `https://esora.app/img/unsafe/1200x0/filters:no_upscale():format(jpeg)/events/{eventId}/{media[0].localFileName}` (first non-disabled image) |
| external_id | `esora-occ-{eventOccurrenceId}` — per-occurrence UUID; one event (artist) plays several nights per week, so the event id alone would collapse occurrences |

Occurrences with `disabledAt`, events with `disabledAt`, and past dates
(relative to today in Asia/Yerevan) are skipped.

## Quirks

- Everything is one page today, but `scrape()` follows `totalPages` (capped)
  in case Esora extends the horizon.
- Esora machine-translates between en/hy/ru; we scrape its per-locale display
  content verbatim (hy canonical, ru+en as translations). Titles are artist
  names and identical across locales.
- The weekly image (`media`) is the same IG line-up poster for every event of
  the week; still worth carrying.
- If the Malkhas source page ever 404s, the club may have moved off Esora —
  re-recon (the eventSourceId is the stable key).

Last verified: 2026-08-18, verified via HTTP fetch (browser unavailable —
browser-use wanted to attach to the user's real Chrome and needs manual
approval, so per policy we fell back to HTTP instead of attaching). Fetched
the live source page (`GET
https://esora.app/en/yerevan/sources/2f85265c-78f0-4a7c-9580-43163182c3cf`)
with httpx; it server-renders the same Redux state inline (`eventOccurrences`/
`events` JSON embedded in a Next.js RSC payload plus a rendered
`SourceEventGrid` DOM with one `<article>` per card: `eyebrow` = relative day +
date + time, `title` = artist name + link to `/en/yerevan/events/{eventId}`).
Cross-checked all 6 live cards against `MalkhasJazzClubScraper().scrape()`
(live network call, not the fixture) — every field agreed:

| date | live page (day · date · time · title · eventId) | scraper output |
|---|---|---|
| 2026-08-18 | Today · 21:00 · Ilona Sagieva · `925dceab-…` | 21:00, "Ilona Sagieva", jazz, price=None, `esora-occ-1677511a-…` → `.../events/925dceab-…` ✓ |
| 2026-08-19 | Tmrw · Aug 19 · 21:00 · Sona Umroyan · `2c0b453c-…` | 21:00, "Sona Umroyan", jazz, price=None, `.../events/2c0b453c-…` ✓ |
| 2026-08-20 | Thu · Aug 20 · 21:00 · Ilona Sagieva · `925dceab-…` | 21:00, "Ilona Sagieva", jazz, price=None ✓ |
| 2026-08-21 | Fri · Aug 21 · 21:00 · Sona Umroyan · `2c0b453c-…` | 21:00, "Sona Umroyan", jazz, price=None ✓ |
| 2026-08-22 | Sat · Aug 22 · 21:00 · Tatevik Balayan · `1209e1c8-…` | 21:00, "Tatevik Balayan", jazz, price=None ✓ |
| 2026-08-23 | Sun · Aug 23 · 21:00 · Aramo · `edd3139d-…` | 21:00, "Aramo", jazz, price=None ✓ |

6/6 events matched on date, time, title, eventId and card order; the live
page shows no price/cost anywhere for any card, confirming `price=None` (not
a scraper omission). 6/6 have an image_url and ru+en translations (both from
the same live scrape). Coverage: title 6/6, date 6/6, time 6/6, category 6/6,
image 6/6, translations 6/6, price 0/6 (source publishes none — expected, see
above), annotations 0/6 (feed tags are `["jazz"]` only, which is the
discriminator and correctly excluded).
