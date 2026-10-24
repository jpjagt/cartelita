# Kiln Theatre — source map

Venue slug: `kiln-theatre` (London) — 269 Kilburn High Road, NW6 7JR.
Categories `theater` and `film` (lists `theater` and `film`, each
whitelisted to its category). Kiln Cinema belongs to this source: keep it
off the Clusterflick whitelist.

Data: Spektrix client `tricycle` via `_spektrix.py` (see
`spektrix_SOURCE.md`). Show pages are joined from **two listings**:
`https://kilntheatre.com/whats-on/` (theatre) and
`https://kilntheatre.com/cinema-listings/` (films), both linking
`https://kilntheatre.com/whats-on/<slug>/`; show pages link each performance
as `…/book/<numeric instance id>`. `spk.scrape` takes one `Site`, so the
module runs the helper's steps itself (`fetch_programme` → two
`site_page_ids` → `site_urls` → `select` → `fetch_prices` → `build`). The
website is behind Cloudflare but plain httpx gets 200.

## Curation

`Type` attribute: **Theatre** → theater, **Cinema** → film (first-run films,
family films, NT Live / event cinema, Q&A screenings). Dropped:
**Supplementary Event** (Audio Description Add-ons — whose `WebEventType` is
"Theatre", so `WebEventType` alone is not enough) and **External Hire**
(Raising Hare: An Evening with Chloe Dalton).

## Quirks

- Films' prices vary per screening (£8 off-peak / £10, £14 event cinema,
  £5 family) — per-instance price lists, used as is.
- Theatre titles are the box office's capitals ("NINE NIGHT", "BERLIN").
- Not joined (Spektrix event page instead): shows on their last day (TABLE
  17, Hadestown on 2026-10-24) and films not yet on the cinema listing (Hay
  Fever, January).
- Access/screening type sits in the string instance attribute
  `AccessPerformance` ("Captioned Screening", "Relaxed Performance", "Parent
  and Baby Screening"); the helper surfaces only boolean flags.

## Verification

Last verified **2026-10-24**, live: 174 performances, 23 events (3 theatre,
20 film), 174/174 priced, 20 linked to kilntheatre.com. Wild Horse Nine: 18
screenings 6–19 Nov — times match the page (Fri 6 Nov 3.30PM / 6.00PM /
8.30PM, Sat 7 Nov 1.00PM …). NINE NIGHT: 51 performances 12 Nov–2 Jan, 19:30
evenings matching "12 Nov–02 Jan 2027".
Cold-start DB: same row count as the scraper output (no collapsed occurrences).
