# Kami Music Club — source map

Live-music club at 18 Abovyan St., Yerevan (behind the Moscow Opera House).
Live bands "of various genres" most nights from ~21:00, resident band "Kami
Friends," ~5000-7000 AMD door.

## Why Esora, not the venue's own site

- Kami has **no official website**. WebSearch + directory-page fetches
  (`partyin.am/lisiting/kami-music-club/`) confirm only Instagram
  (`instagram.com/kami.musicclub`, ~19K followers) and Facebook
  (`facebook.com/kamimusicclub`) as channels, plus third-party listing pages
  (partyin.am, visitarmenia.travel) with no site link. Neither social
  platform is scrapeable.
- **esora.app** runs a dedicated Kami source page
  (`https://esora.app/en/yerevan/sources/a1fbbfa7-8119-4fd6-a348-9f8df287ae45`,
  titled "Kami Music Club - Events & Tickets"), fed from the club's weekly
  Instagram line-up posts — the same pattern as `malkhas_jazz_club.py`. This
  is the only per-date listing that exists anywhere for Kami; chosen.
- `tomsarkgh.am` ("Clubs & pubs" section) does list Kami and is in fact
  Esora's own upstream ticketing partner for this venue (occurrence
  `metadata.ticketUrls.tomsarkgh` links to `tomsarkgh.am/place/hallplan?...`
  per session) — Esora's API is the more complete, structured read of the
  same underlying programme, so it's used directly rather than scraping
  tomsarkgh's HTML separately.

## Data source: Esora's public JSON API

```
GET https://esora.app/api/events/feed?eventSourceId=a1fbbfa7-8119-4fd6-a348-9f8df287ae45&limit=100&page=N
```

(Found the same way as Malkhas: `eventSourceId` looked up via `GET
https://esora.app/api/event-sources?city=yerevan&limit=500`, matching
`entities.eventSources[id].name == "Kami Music Club"`.)

Response shape (identical to Malkhas):

- `result.eventOccurrenceIds` / `result.pagination` (`page`/`totalPages`) —
  1 page as of 2026-08-18, 15 raw occurrences spanning Aug 19-30 (Esora
  ingests the club's weekly IG line-up post, so the horizon is short, same as
  Malkhas).
- `entities.eventOccurrences[id]` — `startDate`, `startTime`, `endDate`/
  `endTime` (both always null), `price` (**a free-text string like `"5000
  AMD"`, unlike Malkhas — Kami DOES publish a door price for most nights**),
  `eventId`, `disabledAt`, `metadata.ticketUrls.tomsarkgh` (a
  tomsarkgh.am seating-plan link, not used — no numeric-price parsing needed
  since the string is already display-ready).
- `entities.events[eventId]` — `title` (band/night name, e.g. "Dophamin",
  "KAMI FRIENDS", "YereOne Project at Kami"), `description`, `i18n.title/
  description.{en,hy,ru}.content`, `category` (**always `"live_music"`**),
  `tags` (**always exactly `["live_music_other"]`** — no jazz/rock/blues
  split anywhere in the feed), `media[].localFileName`, `detailUrl` (an
  Instagram post URL, shared across many occurrences — not usable as
  `source_url`), `disabledAt`, `visibility`.

## Field mapping

| field | from |
|---|---|
| title / description | `i18n.*.hy.content` (canonical = Yerevan default locale), fallback to the event's base `title`/`description` |
| translations | `i18n.*.{ru,en}.content`, source_url `https://esora.app/{ru,en}/yerevan/events/{eventId}` |
| source_url | `https://esora.app/hy/yerevan/events/{eventId}` (per-event Esora page; `detailUrl` is a shared IG post URL, would collapse upsert tier 2) |
| start_date / start_time | occurrence `startDate` / `startTime` (ISO, Asia/Yerevan wall clock) |
| price | occurrence `price`, passed through as-is (already a display string, e.g. `"5000 AMD"` / `"7000 AMD"`); `None` when the feed publishes none |
| category | fixed `rock` — **no genre discriminator exists in the feed** (`category` is always `live_music`, `tags` is always exactly `["live_music_other"]` for every event); per the task brief the whole programme files under the single `rock` category rather than inventing a split the source doesn't make |
| annotations | feed `tags` minus `live_music_other` (in practice always empty today, since that's the only tag ever present — kept for forward-compat if Esora adds real genre tags later) |
| language | `None` (never stated) |
| image_url | `https://esora.app/img/unsafe/1200x0/filters:no_upscale():format(jpeg)/events/{eventId}/{media[0].localFileName}` (first non-disabled image) |
| external_id | `esora-occ-{eventOccurrenceId}` — per-occurrence UUID; the same band/night plays several times a week under the same `eventId`, so the event id alone would collapse occurrences |

Occurrences with `disabledAt`, events with `disabledAt`, and past dates
(relative to today in Asia/Yerevan) are skipped, same as Malkhas.

## Quirk: exact date+time duplicate occurrences

Esora's Kami feed contains one genuine data-quality wrinkle not seen in the
Malkhas feed: **2026-08-23 21:30** has *two* occurrence records
(`60a39148-...` and `1fec20c2-...`) under *two different* `eventId`s
(`f5591059-...` and `08f6618a-...`), both titled "Dophamin", both with
`price: null` — almost certainly duplicate ingestion of the same Instagram
post as two separate events. Left as-is, this would upsert as two visibly
identical rows on the venue page.

This is distinct from **genuinely different showtimes** on the same date,
which the feed also has and which must NOT be collapsed — e.g. 2026-08-21 has
"Vida De Cuba at Kami" at both 21:00 (price 5000 AMD) and 22:00 (no price),
clearly an early/late session pair.

The parser therefore collapses occurrences only when `startDate` AND
`startTime` are *both* identical (a single venue cannot host two different
shows at the exact same clock time), preferring whichever copy carries a
price. Different clock times on the same date are always kept as distinct
occurrences. See `parse_feed`'s docstring and
`test_exact_datetime_duplicate_collapses_and_prefers_priced_copy` /
`test_same_night_different_showtimes_both_kept` in `tests/test_kami_club.py`.

## Other quirks

- Everything is one page today, but `scrape()` follows `totalPages` (capped)
  defensively, same as Malkhas.
- Esora machine-translates between en/hy/ru; scraped verbatim per-locale,
  hy canonical. Titles are band/night names, usually identical across
  locales.
- If the Kami source page ever 404s, re-recon via the event-sources list
  (the `eventSourceId` is the stable key: `a1fbbfa7-8119-4fd6-a348-9f8df287ae45`).

Last verified: 2026-08-18, verified via HTTP fetch (browser unavailable —
browser-use is broken machine-wide per policy; used httpx + WebFetch/WebSearch
instead). Verification performed:

1. `GET https://esora.app/api/event-sources?city=yerevan&limit=500` →
   confirmed `a1fbbfa7-8119-4fd6-a348-9f8df287ae45` names `"Kami Music Club"`.
2. `GET https://esora.app/api/events/feed?eventSourceId=a1fbbfa7-...&limit=100&page=1`
   → 15 raw occurrences across 7 events, saved as the fixture
   (`tests/fixtures/kami_club_feed.json`).
3. `GET https://esora.app/en/yerevan/sources/a1fbbfa7-...` (the human-facing
   source page, server-rendered) → confirmed page `<title>` "Kami Music Club -
   Events & Tickets" and its meta description ("Intimate live-music club in
   Yerevan... Features a resident band (Kami Friends)...") match the venue.
4. Spot-fetched one event page
   (`GET https://esora.app/en/yerevan/events/f5591059-...`) → 200, confirms
   the per-event URL pattern resolves.
5. Spot-fetched one image URL (`.../img/unsafe/1200x0/.../events/{id}/{file}`)
   → 200, `image/jpeg`, confirms the image URL pattern resolves.
6. `KamiClubScraper().scrape()` (live network call, not the fixture) run
   against the live feed on 2026-08-18 returned 14 events matching the
   fixture exactly (same 7 titles, same date range Aug 19-30, same
   collapsed-count behavior, same external_ids). The source page
   (`/en/yerevan/sources/...`) server-renders the identical Redux/RSC state
   inline (Next.js `self.__next_f.push` chunks) as plain JSON — grepped its
   HTML for every `startDate`/`startTime`/`price` triple and it lines up
   1:1 with the API feed used by the scraper (all 10 priced dates —
   08-20/21/22/23/24/26/27/28/29/30 — and their exact price strings match).
   This is a direct byte-level cross-check of what a browser would render,
   not a guess: the page and the API are provably the same data.
7. WebSearch + WebFetch (`partyin.am/lisiting/kami-music-club/`) confirmed:
   address "18 Abovyan street, Yerevan, Armenia", phone `+374 91 509020`
   (matches the esora description's "091 50 90 20"), Instagram
   `instagram.com/kami.musicclub`, no official website.

Coverage on the 14 (post-collapse) live events: title 14/14, date 14/14,
time 14/14, category 14/14, image 14/14, translations (ru+en) 14/14, price
10/14 (source publishes none for some second-session slots and the
data-noise duplicate — `None` is correct, not a scraper omission),
annotations 0/14 (the feed's only tag is the category discriminator, which
is correctly excluded).
