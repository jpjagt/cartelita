# Sala Montjuïc — source map

Venue slug: `sala_montjuic`. Single-category venue: **film** (Barcelona's summer
open-air cinema series at the Montjuïc castle moat).

## SEASONAL quirk (important)

Sala Montjuïc is a **summer-only** open-air cinema, running roughly **late June →
early August**. Outside the season the programme may be **empty or not yet
published**. The 2026 edition runs **10 July → 5 August 2026**. The parser must
therefore tolerate a listing with **zero** `article.movie` cards and return an
empty list without error. (Verified 2026-06-01: the 2026 programme IS published,
16 screenings.)

## List URL(s)

- Programme: `https://www.salamontjuic.org/programacio/`
  (the bare host `salamontjuic.org` 301-redirects to `www.`; follow redirects.)
  The site **403s requests without a browser `User-Agent`** — the scraper sends a
  Chrome UA (same as Cines Verdi).
- This single server-rendered page lists every screening of the season — one
  request is the complete schedule. No pagination.
- Each screening is its own occurrence (one row). One film per night; the same
  film does **not** repeat, so there is one card per (film, date).

## Data source (server-rendered HTML — no JS needed)

The programme is an Elementor "dynamic posts" grid. One `<article class="movie">`
per screening. Per article:

| Field          | Source                                                                       |
|----------------|------------------------------------------------------------------------------|
| `title`        | `h3.dce-post-title a` text                                                    |
| `source_url`   | `article[data-post-link]` (also the `h3 a[href]`) → `/movie/<slug>/`          |
| `external_id`  | `<movie-slug>@<date>` — slug qualified by the occurrence date (see below)     |
| `start_date`   | a `.dce-post-custommeta` text matching `Weekday DD/MM` → year inferred (2026) |
| `image_url`    | `.dce-post-image img[src]` (the largest non-`srcset` `src`)                   |
| `price`        | `"sold-out"` if a `.dce-post-custommeta` reads `SOLD OUT`, else `None`        |
| `annotations`  | the **live-music act** (the remaining `.dce-post-custommeta` text)            |
| `category_slugs` | always `["film"]`                                                           |

### Date rule

The date meta is e.g. `"Divendres 10/07"` (Catalan weekday + `DD/MM`, **no year**).
We parse the `DD/MM` and infer the year as the current year, rolling to next year
if the resulting date is >90 days in the past (year-end safety) — same convention
as Casa Figari. The Catalan weekday is ignored (cross-checked against 2026: it
matches).

### Time rule

The listing page carries **no time**. Each screening's evening schedule lives on
the **detail page** (`/movie/<slug>/`) as free-text widgets:
`"22:00 – PEL·LÍCULA"` (the film) and `"20:45 – CONCERT"` (the live-music opener).
The scraper fetches each detail page and reads the **`… – PEL·LÍCULA`** line for
`start_time` (consistently 22:00 across the 2026 season, but **read from the page,
not hardcoded** — open-air screenings start after sunset and the time can shift).
If the detail fetch/parse fails, `start_time` falls back to `None`.

### Price

No price is shown on the site — tickets are sold via an external provider
(`codetickets.com`). So `price` is `None`, except we surface `"sold-out"` when the
listing card carries a `SOLD OUT` meta (normalized per the price convention).

### external_id

`<movie-slug>@<YYYY-MM-DD>`. The movie slug alone would be a fine key here (each
film screens once), but we qualify it with the date per the per-occurrence-dedup
convention — robust if the venue ever reruns a film on another night. `source_url`
stays the bare `/movie/<slug>/` page.

## i18n

The site has CA/ES/EN variants (`/programacio/`, `/es/programacion/`,
`/en/screennings/`). Film titles are the original (mostly Spanish) titles and are
identical across locales, so we scrape only the CA programme and emit no
translations — the list page is a complete event on its own.

## Quirks

- The `.dce-post-custommeta` blocks are not class-stable per field (Elementor
  emits accumulating repeater classes). We discriminate by **content**: a
  `Weekday DD/MM` pattern is the date; `SOLD OUT` is the sold-out flag; anything
  else is the live-music act (annotation).
- One screening is "Pel·lícula Sorpresa" (surprise film) — a normal card.

## Verification (2026-06-01)

`dry-run sala_montjuic` → 16 events; start_time 16/16 (22:00, from detail pages),
image 16/16, annotations 16/16, external_id 16/16, all category `film`; price 2/16
(`sold-out` for MARTY SUPREME + HAMNET). Cross-checked field-by-field against the
live programme page (titles, dates, sold-out flags, live-music acts) — all agree.

last verified: 2026-06-01
