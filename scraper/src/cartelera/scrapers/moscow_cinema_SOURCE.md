# Moscow Cinema (Kino Moskva) — source map

Venue slug: `moscow-cinema`. Yerevan's historic cinema at 18 Abovyan St (Charles
Aznavour Square), multiple halls (Red/Blue big + small halls, VIP; a summer
open-air hall appears as its own hall name when programmed). Single-category
venue: **film**.

## Source choice

The venue's own site — `https://www.moscowcinema.com/en` — **server-renders the
whole 7-day schedule on the homepage**. No XHR/API is involved (the earlier 403
did not reproduce; see Quirks). Rejected fallbacks: kinoafisha/tomsarkgh
aggregators (less direct, no synopsis, and the venue's own page has everything).

## List URL

- `https://www.moscowcinema.com/en` (English; `/am` and `/ru` are the same site
  in Armenian/Russian — we scrape `en` only).
- The homepage carries a 7-day date strip (`.Schedule-date__item`,
  `data-id="schedule-N"`, `p.date` → "Today 18.08" / "Thu. 20.08") and one
  schedule table per day (`div#schedule-N.ScheduleTable__wrapper`). Days beyond
  the published window simply have empty/tiny tables (observed: today+4 onward
  thins out fast — the venue publishes ~4 days of showtimes at a time).
- `/en/ongoing` lists the same films; a film with no sessions in the window
  (e.g. `winepress` on 2026-08-18) has zero schedule rows everywhere, so the
  homepage tables are the complete session source.

## Data source (CSS selectors)

Per session row (`#schedule-N tbody tr`), reading the desktop `hidden-mobile`
cells (the mobile `mobile-info` span duplicates hall/price/lang — ignore it):

| Field        | Source                                                            |
|--------------|-------------------------------------------------------------------|
| time         | `.ScheduleTable__time span` ("17:45")                             |
| `title`      | `.ScheduleTable__movie .movie-name a` text                        |
| `source_url` | same `a[href]` → `/en/ongoing/<slug>`                             |
| hall         | `.ScheduleTable__hall span` ("Red Hall", "VIP", …) → annotations  |
| `language`   | `.ScheduleTable__lang` ("In Armenian", "In Russian with Armenian subtitles", "French, Armenian, English, subtitles: Armenian") — kept verbatim (only whitespace/trailing comma trimmed), never inferred |
| age          | `.ScheduleTable__age` ("15", "ԾՈՒ", …) — not emitted (Armenian rating codes, meaningless without context) |
| price        | `.ScheduleTable__price` ("2000 ֏", AMD)                           |

The date for `#schedule-N` comes from the matching date-strip item's `p.date`
`DD.MM` text; the year is resolved relative to today (the strip is always
today…today+6, so pick the year that lands the date within that window).

Per film **detail page** (`/en/ongoing/<slug>`, one fetch per unique film,
~15–20): `description` from `.description-item .lighten-txt`; `image_url` from
`meta[name="og:image"]` (poster webp); Genre from the `.fs18-13.d-grid`
label/value list → annotations. A detail fetch failure degrades gracefully
(schedule fields still emitted).

## Event shape (film-scraper convention) & `external_id`

**One ScrapedEvent per (film, day)** — all of that day's sessions in
`start_times` (sorted; `start_time` = earliest). `external_id` =
`<film-slug>@<YYYY-MM-DD>` — per-occurrence (per day), so re-scrapes upsert
cleanly and later days never collapse into earlier ones (the Filmoteca trap).
The per-session "Buy a ticket" href (`/en/halls/<sessionid>`) is a finer id but
unneeded at day granularity.

## Category rule

Single category: everything in the schedule is `film`. Genre ("Psychological
thriller", …) and hall names go to `annotations`.

## Price

Prices are per session, in AMD, shown verbatim ("2000 ֏"). When a day's sessions
differ: range `"<lo>–<hi> ֏"` only if hi ≥ 2×lo (VIP vs regular commonly
qualifies), else the single highest — the shared 2× convention, hand-applied
because `format_eur_range` is euro-only.

## Quirks

- An earlier probe of the site returned **403 to plain httpx**; on 2026-08-18
  both default and browser UAs got 200. The host sits behind Cloudflare, so the
  scraper sends a desktop browser UA anyway as insurance.
- "Today"'s table only shows *remaining* sessions (past showtimes are dropped
  server-side), so today's counts shrink over the day.
- The date strip has 7 items but far days may have zero rows — an empty table is
  normal, not a parse failure.
- Schedule badges ("Special price", "Premiere") sit on the date strip, not on
  rows; not scraped.

## Verification

Verified via direct httpx fetch against the live site on 2026-08-18 (browser not
needed: plain httpx — with or without the desktop UA — returned 200, matching the
"no 403 reproduced" note above). Cross-checked schedule-0's first 6 session rows
(13 Kilometers from the Tunnel, Moana RUS, The ghost between us ×2 rows, Spider-Man:
Brand New Day ×2 rows, In the Land of Arto) field-by-field — title, href, time,
hall, language (incl. the trailing-comma trim on the multi-language label), price
— against `parse_schedule`'s output; all matched, including the range-vs-single-
highest price collapse for Spider-Man (2500/5000 → "2500–5000 ֏", hi ≥ 2×lo) and
The ghost between us (differing tiers < 2× → single highest). Also fetched
`/en/ongoing/13-kilometers-from-the-tunnel` live and confirmed `parse_film_detail`
matches (description, poster, genre). Live per-day session totals
(10/24/24/25/2/1, 52 film-day events total) matched the fixture exactly (fixture
was captured the same day) and, after a cold-start `cartelera run moscow-cinema`
into a scratch DB, matched the DB row counts exactly — confirming `external_id`
does not collapse occurrences. 100% field coverage (price/language/annotations/
description/image_url) across all 52 live events. Re-running the scraper against
the same DB left the row count unchanged (idempotent upsert).

last verified: 2026-08-18
