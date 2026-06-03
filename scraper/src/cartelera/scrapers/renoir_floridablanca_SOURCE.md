# Renoir Floridablanca — source map

Venue slug: `renoir_floridablanca`. Independent/arthouse cinema (Cines Renoir
chain, Barcelona location). Single-category venue: **film** (every session is a
film screening; no sub-categorization).

## List URL(s)

- Daily cartelera: `https://www.cinesrenoir.com/cine/renoir-floridablanca/cartelera/`
  - Defaults to **today**. A specific day is selected with `?fecha=YYYY-MM-DD`.
  - The page exposes a `<select id="elige-dia">` whose `<option>` values are the
    available days (today + the next 6 days, i.e. ~7 days of programming). The
    scraper iterates over those option dates, fetching one page per day.
  - NOTE: the path is `/cine/renoir-floridablanca/cartelera/` (found via the
    homepage link). The `/cartelera/barcelona/renoir-floridablanca/` URL from the
    brief returns HTTP 500 — do not use it.

## Data source (server-rendered HTML — no JS, no JSON blob)

No JSON-LD / `__NEXT_DATA__`. One film block per movie, rendered three times in
responsive variants; we read the **desktop** variant only to avoid triplicates:
`div.my-account-content.mb-15.d-none.d-lg-block`. Per block (inside `.row`):

| Field        | Source                                                                   |
|--------------|--------------------------------------------------------------------------|
| `title`      | `.col-4 a[href^="/pelicula/"]` text                                       |
| `source_url` | that `a[href]` → `/pelicula/<slug>/` (absolutized)                        |
| director     | first `.col-4 small > b` text → into `description` ("de <Director>")      |
| version      | a `.col-4 small` containing "Versión"/"V.O" (VOSE/VOSC) → `annotations`   |
| age rating   | a `.col-4 small` containing "recomendada"/"Apta" → `annotations`          |
| `image_url`  | `.col-1 a img[src]` (poster; site-relative or pillalas CDN, absolutized)  |
| showtimes    | `.col-7 .pase-cartelera` — one per session (see below)                    |

### Showtimes / occurrences

Each `.pase-cartelera` is one screening session:
- time: the `a[href*="pillalas.com/pase/"]` link text (`"18:00"`). The buy button
  is usually `a.btn-primary`, but special events use `a.btn-evento` — match by the
  `pillalas.com/pase/` href, NOT the button class.
- `sala`: the first `span` (e.g. "sala 06").
- `pase id`: `pillalas.com/pase/<ID>/` — **unique per session** (verified 28/28
  unique on one day). This is the `external_id`.
- optional `.pase-cartelera-tag` (e.g. "PASE ESPECIAL") → `annotations`.

**One `ScrapedEvent` per (film × session)** — i.e. per `.pase-cartelera`, not per
film. A film screens at several times per day and on several days, so the
occurrence is the session. `start_date` = the page's selected `?fecha`, `start_time`
= the session time.

### `external_id`

The pillalas `pase` id (`pase-<ID>`). It is unique per session, so it is already a
per-occurrence key — no date/time qualification needed (unlike Filmoteca, whose id
was a film slug shared across screenings). Blocks/sessions with no `pase` link are
skipped (no reliable occurrence to emit).

### Date rule

`start_date` comes from the page itself: the `<select id="elige-dia">`
`<option>` whose text contains "seleccionado"/"selected" carries
`...?fecha=YYYY-MM-DD`. This makes fixture parsing deterministic and matches the
day actually rendered. Falls back to today's date if the marker is absent.

## Price

The cartelera carries **no per-screening price**. Renoir's price table
(`/cine/renoir-floridablanca/precios-promociones/`) is heavily tiered by day of
week and audience (weekday general 8,50 €, weekend/holiday 9,80 €, "día del
espectador" Mon/Wed 5,50 €, promos, collectives…). Parsing it per-day is fragile
and locale-bound, so we apply a single concise general-admission range
**`"8,50–9,80€"`** (weekday→weekend general adult ticket) to every event as a
static default, per the price convention (skip member/discount tiers; show a range
only when tiers differ meaningfully — here weekday vs weekend genuinely differ).

## category

Always `["film"]`. list_memberships: `film`.

## i18n

Site is Spanish (`Content-Language: es`); no per-event translation pages worth
scraping. No translations emitted.

## Quirks

- Each film block is rendered 3× (responsive `d-lg-block` / `d-md-block` /
  `d-sm-block` variants). Use only `.d-none.d-lg-block` or you triple every event.
- `/cartelera/barcelona/renoir-floridablanca/` (brief's URL) → 500. Use
  `/cine/renoir-floridablanca/cartelera/`.
- Posters may be hosted on `media.pillalas.com` (already absolute) or
  site-relative under `/media/Peliculas/Cartel/`.

last verified: 2026-06-01
