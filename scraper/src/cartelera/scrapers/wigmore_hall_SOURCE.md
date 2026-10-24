# Wigmore Hall — source map

Venue slug: `wigmore-hall` (London) — 36 Wigmore Street, Marylebone
W1U 2BP. Categories `classical`, `jazz`, `kids` (lists `classical`, `jazz`,
`kids`, each whitelisted to its category).

## Data source

The hall's own JSON API (its Next-style site, Tessitura behind it), plain
httpx with `CARTELITA_COMPAT_UA`:

`GET https://www.wigmore-hall.org.uk/api/v1/listings/whats-on?page=N`
→ `{items: [{node}], totalItems, totalPages}` (12 per page; 296 items on
2026-10-25). The API takes the what's-on page's own filter options as query
parameters (the options are listed in the page's embedded `filters` JSON);
**a repeated parameter is a union** (`genres=jazz&genres=global` → 11 =
6 + 6 − 1), a comma list matches nothing.

## Curation (the site's own filters)

Four filtered listings, all pages each (~30 requests per run):

| Group | Query | Our category |
|---|---|---|
| classical | `genres` = chamber, choral, contemporary, early-music, global, piano, song, string-quartet | classical |
| jazz | `genres=jazz` (6 on 2026-10-25: Emmet Cohen, Brad Mehldau, Patricia Brennan…) | jazz (+ classical when also in a classical genre, e.g. Brad Mehldau = jazz + piano) |
| kids | `learningGenres=events-for-families` (22: Family Concerts, Chamber Tots, For Crying Out Loud!, family workshops) | kids |
| drop | `learningGenres` = events-for-schools, music-for-the-moment (dementia-friendly concerts), imagine-series (neurodivergent audiences) | — |

A performance in "drop" is left out even when it is also in a genre (the
two Music for the Moment concerts are also "chamber"). Anything in **no**
filter is dropped (2026-10-25: a members' open rehearsal and the
"Such the tenor man told" talk).

Known residue: the site files some talks/masterclasses under a genre too
(pre-concert talks → Early Music, ECMA masterclass, a Nigerian Art Music
talk → Global; ~6 of 290), so they show as classical. The listing gives no
signal to tell them apart (only the event page's credit roles "speaker"),
and they are classical-music events at the hall.

## Fields

| Field | Source |
|---|---|
| `title` | `title` (plain; `titleOverrideText` has `<sub>` role markup) |
| `start_date`/`start_time` | `date` (ISO with offset) → Europe/London |
| `price` | `pricesText`: `<sub>` small print removed ("+£1 booking fee"), then `gbp_price` — "£45 £38 £34 £27 £18" → "£18–45", "£18 (concessions £16)" → "£18", "Children £6, Adults £8" → "£8", "Free"/"Free (ticket required)" → "free" |
| `description` | `subtitleText` (the programme: "Barber, Mark Simpson and Nielsen") |
| `source_url` | `https://www.wigmore-hall.org.uk` + `url` (`/whats-on/YYYYMMDDHHMM`) |
| `external_id` | `tessituraId` (per performance) |
| `image_url` | `listingImage.x2` / `src` |

## Verification

Last verified **2026-10-25** via HTTP cross-check against the event pages'
own embedded props (`dateText`, `pricesText`): 290 performances (266
classical, 6 jazz, 22 kids), 100% priced, 100% timed. Soloists of the
Kronberg Academy — page "Sun 25 Oct 2026, 7.30pm", "£40 £37 £33 £27 £18" →
scraper 25 Oct 19:30 "£18–40"; Timothy Ridout (Viola Day) — "Sat 14 Nov
2026, 11.30am", "£18 (concessions £16)" → 11:30 "£18"; Chamber Tots — "Wed
28 Oct 2026, 10.15am", "Children £6, Adults £8" → kids, "£8"; Emmet Cohen
Quintet — "Mon 02 Nov 2026, 7.30pm" → jazz, "£18–50". Cold-start DB: rows
= scraper output (see the batch report).
