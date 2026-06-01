# Filmoteca de Catalunya — source map

Venue slug: `filmoteca`. Single-category venue: **film** (every session is a film
screening; the venue does not sub-categorize).

## List URL(s)

- Weekly agenda: `https://www.filmoteca.cat/web/ca/view-agenda-setmanal`
  - Defaults to the current week. A specific week is selected with `?w=YYYY-MM-DD`
    (a **Monday**); the page renders that Monday→Sunday.
  - The scraper fetches the current week plus the next few weeks by stepping the
    `?w=` param forward by 7 days, so it covers upcoming programming, not just the
    current week.
- Filmoteca is **closed Mondays**, so a week typically shows Tue→Sun.

The "Agenda" page also has a `.listado-agenda` sidebar block ("Tota la setmana")
that lists week-level *exhibitions/cycles* — NOT the daily screenings. Ignore it.
The screenings live in the `.block-day` sections below it.

## Data source (server-rendered HTML — no JS needed)

Structure: one `.block-day` per calendar day, each with an `<h2>` day heading and
a swiper of `.card` elements (one per screening). Per `.card`:

| Field          | Source                                                                 |
|----------------|------------------------------------------------------------------------|
| `title`        | `.content-card .titl a` text                                           |
| `source_url`   | `.content-card .titl a[href]` → `/web/ca/film/<slug>` (abs-ified)      |
| `external_id`  | `<film-slug>@<date>T<HHMM>` — slug qualified by the occurrence (below)  |
| `start_time`   | `.content-card-header .hour` text (`"17:00"`) — **local wall-clock**   |
| `start_date`   | the `dates=YYYYMMDD...` in the Google-Calendar link's `data-content`   |
| `description`  | `.content-card > .description.mini_text-1` (alt title) + director line |
| `image_url`    | `.header-card img[src]` (abs-ified)                                    |
| `annotations`  | `.text-alternative a` text — the **cicle** (e.g. "JAPANIMERAMA")       |
| `category_slugs` | always `["film"]`                                                     |

### Date / time rule

`.hour` is the reliable **local** time. The Google-Calendar `data-content`
attribute carries `dates=YYYYMMDDThhmmss` in **UTC**; we use only its **date**
part for `start_date` (afternoon/evening screenings never cross a UTC day
boundary) and take the time from `.hour`. This avoids week-param month-rollover
arithmetic and any timezone math on the time itself.

`price`: the screening cards carry **no** price. Filmoteca charges a flat
single-ticket rate, read once from the practical-info page
(`/web/ca/informacio-practica`) — the "Entrada individual*" row of the price
table (an `<li>` with a `.text-entrada` label + `N €`, currently **4 €**) — and
applied to every event as `default_price`. If that fetch/parse fails, price falls
back to None (best-effort). It is NOT a per-session price.

`external_id`: the film slug **qualified by the occurrence's date+time**
(`<film-slug>@YYYY-MM-DDTHHMM`). The detail-page slug alone is shared across every
screening of that film (e.g. a Fritz Lang retrospective title runs on many dates),
and the upsert dedups on `(venue, external_id)` — so a bare slug would make later
screenings overwrite earlier ones (real bug found 2026-06-01: June 2's Spione and
Wendy & Lucy were clobbered by later-week screenings of the same films). The
`source_url` stays the bare film page.

## i18n

The agenda is available per-language under `/web/{ca,es,en}/view-agenda-setmanal`.
Titles are frequently already multilingual in the `ca` listing (e.g.
"Nationalité: immigré | Mes voisins"), and per-film detail pages have hreflang
alternates. We scrape only the `ca` weekly agenda (one request per week) and emit
no translations — the list page is a complete event on its own.

## Quirks

- `.category` on each card is always empty for Filmoteca (no sub-categories).
- Monday weeks show no screenings (closed). An empty week is normal, not an error.

last verified: 2026-06-01
