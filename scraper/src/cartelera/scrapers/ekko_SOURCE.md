# EKKO — source map

Venue slug: `ekko` (Utrecht). Categories **pop**, **club**; lists `pop`
(whitelist pop) and `club` (whitelist club). Bemuurde Weerd WZ 3.

Client: plain httpx (`http.fetch`) with the Cartelita UA. ~65 detail fetches
per run (6 parallel).

## List URL

`https://ekko.nl/agenda/` — one server-rendered page with every upcoming
event (`/agenda/page/2/` returns the same list). Rows: `a.event-line-item`.

| Field | Source |
|---|---|
| `external_id` | URL slug (`/event/<slug>/`; each occurrence has its own post, e.g. `dry-cleaning-1`/`-2`) |
| `title` | row `h3` + the support `span` next to it ("FENNE" + "+ Sophie Koole") |
| `start_date` | row date div ("do 15 okt"; a 2-digit year is appended when not the current year: "vr 15 jan 27"); year-less dates resolve to the nearest occurrence not >60 days in the past |
| `category_slugs` | the venue's type filter `data-filter-value`: `concert` → pop, `club` → club (both possible, e.g. Le Guess Who?) |
| `annotations` | remaining filter values (`overig`, `ekko40`) |

Detail page (`/event/<slug>/`): key/value blocks `div.uppercase.leading-tight`
(two child divs: Datum / Open / Aanvang / Eindtijd / Locatie / Leeftijd).

| Field | Source |
|---|---|
| `start_time` | "Aanvang" (fallback "Open") |
| `price` | the ticket button: "Koop tickets \| € 15.5" → `"15,50€"`; "Uitverkocht" → `"sold-out"`; "Gratis toegang" → `"free"`; free reservation "€ 0.00" with a door price in the note ("Aan de deur altijd €5,50") → the door price; festival day tickets in the note ("Vrijdag €36,50 \| Zaterdag €51,50") → the event weekday's price; "Tickets via Le Guess Who?" → None |

## Exclusions

- Rows with neither `concert` nor `club` (only `overig`/`ekko40`): the "Is
  This It? De Popquiz" quiz afternoons/evenings and a cabaret night — not
  concert/club programme.
- **Off-site shows** EKKO presents elsewhere (row has a location label; detail
  "Locatie" ≠ EKKO): De Kromme Haring, ACU (owned by the `acu` source),
  Jacobikerk. One owning source per venue.
- "Eten in EKKO" rows (restaurant, not `/event/`).
- Cancelled: ticket button "geannuleerd"/"afgelast".

## Quirks

- Kept as the venue labels it: karaEKKO (club-labelled karaoke club night).
- Tickets on Stager — never fetched.

## Verification

Last verified: **2026-10-14 via HTTP cross-check.** Live: 62 events,
2026-10-15 → 2027-05-15; time 62/62, price 60/62 (None: the two Le Guess Who?
days), 48 pop / 16 club. Independent check: first 8 events' detail pages
re-parsed with regexes (Aanvang, button text/amount, door note) — 8/8 agree.
