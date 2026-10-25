# Southbank Centre (`southbank-centre`)

One venue (RFH, QEH, Purcell Room, Clore Ballroom on one site; the hall is an
annotation). One owning source for classical, theater, dance, kids, pop, jazz
(list memberships whitelisted per category).

## Data sources (website only, curl_cffi `impersonate` — Cloudflare)
- Listings `https://www.southbankcentre.co.uk/whats-on/?artform-filter=<f>`
  for classical-music, gigs, performance-dance, family; pagination
  `/whats-on/page/N/?artform-filter=<f>`. Card: `a.c-event-card__cover-link`
  + `.c-event-card__primary-artform` (primary artform). Only cards whose pill
  is mapped are fetched.
- Event page: JSON-LD event per performance (`MusicEvent`/`TheaterEvent`/
  `ChildrensEvent`): `startDate` (with offset), `location.name`, `offers`
  (AggregateOffer low/high → `format_gbp_range`; Offer price 0 → "free";
  `availability` SoldOut → "sold-out" except free drop-ins, which the site
  flags SoldOut because nothing is bookable). Masthead: title, intro
  (description), primary-artform pill, series (`.c-event-masthead__group-item`
  → `/events/<series>/`, also annotations).
- external_id: `<page slug>@<YYYY-MM-DDTHH:MM>` (JSON-LD has no perf id).
- TNEW (`secure.southbankcentre.co.uk`) is open but not used: it sells
  seating products as separate same-time performances (Cirque Alice 68 rows
  for 34 shows) and has no category.

## Category rule (the site's primary artform)
Classical music → classical; Performance & dance → theater + dance (**owner
review**: one site label covering both; every page is a JSON-LD TheaterEvent,
no finer split; it holds cabaret, circus, live art and dance); Family → kids;
Gigs → pop, or jazz when in the series "EFG London Jazz Festival" (the
site's own series; there is no genre under "Gigs", so folk/world gigs land in
pop and the LJF's non-jazz bookings — Ben Folds, Mariza — in jazz). Dropped:
Literature & poetry, Talks & debates, Comedy, Art & exhibitions, Courses &
workshops, Tours & activities, Online events, Young people (also when a
mapped filter lists them as secondary artform).

## Verification (2026-10-25)
217 listed cards, 211 fetched, 400 events (classical 170, theater+dance 99,
kids 90, pop 27, jazz 14), 99.5% priced. DB rows = 400. Checked: Edward
Gardner Conducts The Dream of Gerontius 2027-04-24 — site JSON-LD
"2027-04-24T19:30:00+01:00", lowPrice 24 / highPrice 86, Royal Festival
Hall, pill "Classical music" → ours 19:30, "£24–86", classical. Alceu
Valença 2026-11-07 19:30 RFH £36–56 → "£56" (2x rule), pop.

## Production (Hetzner IP), 2026-10-25 — does not work
Cloudflare challenges the production server (`cf-mitigated: challenge`,
httpx / curl_cffi / headless browser alike, no clearance) on every path
except the first page of `/whats-on/` (with any query, e.g. each
`?artform-filter=…`): listing pages 2+ (`/whats-on/page/N/…`), every event
page and the sitemaps answer 403. The first page per filter gives 12 cards
(title, primary artform, date range, hall) — no performances, times or
prices; the per-performance data is only on event pages (JSON-LD). Not
date-filterable either (`start-date`/`end-date` ignore the artform filter).
TNEW (`secure.southbankcentre.co.uk`) is an Imperva-tarpitted Tessitura host
(see tnew_SOURCE.md). Nothing open carries the programme, so the module is
unchanged and fails in production (the run's "intermittent" 403 was the
first paginated listing page).
