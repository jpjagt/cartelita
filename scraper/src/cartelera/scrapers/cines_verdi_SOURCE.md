# Cines Verdi Barcelona — source map

Venue slug: `cines_verdi`. Single-category venue: **film** (an independent
arthouse cinema; every session is a film screening, no sub-categories). Two
screens in Barcelona under one site: **Verdi** (Sala 1/2/3…) and **Verdi Park**
(halls named "… V.Park" / "Sala D V.Park"). Both are scraped as one venue.

## Site / URLs

- Canonical homepage `https://www.cines-verdi.com/` is only a city chooser
  (Barcelona / Madrid). The real Barcelona site is the subdomain
  **`https://barcelona.cines-verdi.com/`**. The old path
  `https://www.cines-verdi.com/es/cinemas/barcelona` from the task brief is dead
  (403 / redirects to an unrelated 404). Use the subdomain.
- Listing page: **`https://barcelona.cines-verdi.com/cartelera`** — server-renders
  one `<article>` per film currently in the programme (35 at last check).
- **Bot protection:** every request 403s unless a browser-like `User-Agent`
  header is sent. The scraper sets one on its httpx client. (The saved fixture was
  fetched with that header.)

## Data source (two steps: HTML stub list → per-film JSON API)

The `/cartelera` HTML gives only film *stubs* — the showtimes are lazy-loaded via
JS (Alpine `x-intersect` → `loadMovieData(imdbid, slug)` → `MovieLine` →
`fetch('/api/get-event-by-imdbid/<imdbid>')`). So:

### Step 1 — parse the cartelera HTML for film stubs

Per `<article x-intersect.once="loadMovieData('<imdbid>','<slug>')">`:

| Field        | Source                                                            |
|--------------|------------------------------------------------------------------|
| `imdbid`     | first arg of `loadMovieData(...)` (e.g. `tt33071426`, `tt36120484-2`) — the API key |
| `slug`       | second arg / `.aside a[href]` (e.g. `/the-drama`) → `source_url`  |
| `title`      | `.info-cartelera-performances header h2` text (page locale = **es**) |
| `image_url`  | `.aside figure img[src]` (the `…-pos.webp` poster)               |

### Step 2 — per film, GET `/api/get-event-by-imdbid/<imdbid>` (JSON)

`result.events` is a list of **versions** (language/projection variants); each
version has a `performances` list — **one performance = one screening occurrence**.
Per performance:

| Field          | Source (`performance`)                                              |
|----------------|--------------------------------------------------------------------|
| `start_date`   | `schedule_date` `"YYYYMMDD"`                                        |
| `start_time`   | `time` `"YYYYMMDDhhmmss"` → local wall-clock `hh:mm`               |
| `external_id`  | `performance.id` (globally unique per screening — verified)        |
| `price`        | `data.tickets.prices` (cents, e.g. `"750"`) → max → `"7,50€"`      |
| `annotations`  | `hall_name` (e.g. "Sala 2", "Sala D V.Park") + version `language`  |
| `category_slugs` | always `["film"]`                                                 |

`title`/`image_url`/`source_url` come from the Step-1 stub (the API has them too —
`result.name` is the title — but the stub carries the page-locale **es** display
title and the poster URL). `result.name` is used as a fallback when the stub lacks
a title.

### Date / time rule

`schedule_date` is the local calendar date and `time` is the local wall-clock
(`time[8:10]:time[10:12]`). No timezone math (these strings are already local).

### Price rule

`data.tickets.prices` are integer **cents** strings (e.g. `"600"`, `"750"`). We
take the **max** public price of the performance and format it Spanish-style:
`"7,50€"`, or `"6€"` when round. Per the price convention this is a concise display
string. `None` if a performance carries no prices.

### external_id

`performance.id` (e.g. `1700027`) — globally unique per screening occurrence,
so no date+time qualification is needed (unlike Filmoteca, whose film slug was
shared across screenings). One ScrapedEvent per performance.

## Quirks

- Some imdbids carry a suffix (`tt36120484-2`) — pass them through verbatim to the
  API; they work.
- A film can have multiple versions (e.g. OV vs dubbed) → multiple performances at
  the same date; each is its own occurrence with its own `performance.id`.
- The article also contains a `<header><h2>` and an `.aside figcaption h2` with the
  same title; we read the `.info-cartelera-performances header h2`.
- `data.available` is currently always `false` in the JSON (it reflects a cache,
  not real ticket availability); we do NOT map it to "sold-out".

## Verification (2026-06-01)

`cartelera dry-run cines_verdi` → **157 events**, 100% coverage on start_time,
price, image_url, annotations, external_id; all category `film`. Cross-checked
date/time/price/hall against the live `/api/get-event-by-imdbid/...` JSON and the
rendered cartelera calendar for "Corredora" (5 screenings, 7€ matinal / 7,50€
evening, Sala D V.Park + Sala 2) and "Conoce a los bárbaros" (3 screenings,
7,50€) — exact match.

last verified: 2026-06-01
