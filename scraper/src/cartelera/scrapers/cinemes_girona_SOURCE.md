# Cinemes Girona — source map

Venue slug: `cinemes_girona`. Independent cinema in Barcelona (Eixample/Gràcia).
Single-category venue: **film** (every article on the cartelera is a film
screening). Non-film special events (cycle col·loquis, etc.) are not separately
listed on the cartelera — they appear only as a promo banner above the films —
so we scope to the film cartelera only.

## List URL

- `https://www.cinemesgirona.cat/es/cartelera` (Spanish). The Catalan version is
  at `/ca/cartelera`. We scrape the `es` page; titles often carry their own
  language tag (VOSE / CAT / CASTELLÀ).
- **Server-rendered HTML, no JS needed** — every film article and all its
  showtimes are in the initial HTML. BUT the host returns **403 to a default
  httpx User-Agent**; a normal browser UA header gets a 200. The scraper sends a
  desktop Chrome UA.
- One page renders the **whole upcoming programme** (current week through several
  months ahead — observed 2026-06-02 … 2026-09-21). No pagination / week-stepping.

## Data source (CSS selectors)

One `<article class="row article-cartelera">` per film. Per article:

| Field         | Source                                                                  |
|---------------|-------------------------------------------------------------------------|
| `title`       | `h2 a` text (e.g. "Cowgirl (CAT)")                                       |
| `source_url`  | `h2 a[href]` → `/<film-slug>` (abs-ified to https host)                  |
| `description` | `.col-md-8 > p` first paragraph (synopsis, Spanish)                      |
| `image_url`   | `figure img.d-none.d-md-block[src]` (desktop poster, bizcochito.es)      |
| genres        | `table a[href*="/cartelera/"]` text → free-form `annotations`            |
| `category_slugs` | always `["film"]`                                                     |

### Showtimes / occurrences (the per-occurrence rows)

Showtimes live in the **desktop** tab panes: `.tabs.tabs-performances .tab-pane`.
Each tab-pane `id` is `<filmid>-<YYYYMMDD>` (e.g. `110461-20260602`). Inside a
pane there are one or more `.row.pelicula` blocks; each has a version label
`<span>` (DIG / VOSE / CATALÀ / CASTELLÀ / VOSI / VOSC) and showtime anchors
`a[title="YYYYMMDD HH:MM"]` whose text is the local wall-clock time (the `href`
goes to the admit-one ticketing site — we keep our own `source_url`, not that).

We emit **one ScrapedEvent per (film, date, time)** occurrence. The date comes
from the pane id's `YYYYMMDD`; the time from the anchor's `title` (and matches
the anchor text). The version label is added to that occurrence's `annotations`.

(There is also a mobile mirror — `.horarios article` + a `<select>` — with the
same data; we read only the desktop `.tabs-performances` to avoid double-counting.)

### `external_id`

`<filmid>@<YYYY-MM-DD>T<HHMM>` — the venue's film id qualified by the occurrence
date+time. The film id (from the pane id) is shared across every screening of the
film, and the upsert dedups on `(venue, external_id)`, so a bare film id would
collapse occurrences (the Filmoteca trap). Qualifying with date+time keeps each
screening distinct and unique within a batch.

## Category rule

Single category: every cartelera article is `film`. Genre tags from the metadata
table (Comedia, Drama, Terror, Òpera, Documental, …) and the version label
(VOSE/CAT/…) go into `annotations`, never into `category_slugs`. The brief notes
the venue occasionally hosts theatre/concerts — those are NOT on the cartelera
page, so out of scope here; if a clearly non-film genre ever appears it stays as
an annotation rather than changing the category.

## Price

The cartelera carries **no per-screening price** (only an "Abonaments Vàlids"
notice). The venue's prices page (`/es/preus`) lists the public (non-member) web
ticket: weekend/festive **9€**, weekday (laborable) **7€**, día del espectador
**5€**. There is no per-screening signal of which tier applies, so — like
Filmoteca — we apply a single default to every occurrence: the range **"7–9€"**
(weekday–weekend public price; member/senior/youth and día-del-espectador tiers
omitted per the price convention). This is a static default, not scraped per
event (the preus page is also UA-gated and the values are stable).

## Quirks

- The "PRÓXIMAMENTE" / "PRÓXIMAMENT" badge (`.comingsoon`) is just a
  release-window flag; such films still carry real, dated showtimes and are
  included.
- httpx gets 403 without a browser User-Agent header (Cloudflare-style gate).
- The page's `script[type="application/ld+json"]` and some image hosts reference
  "cines-verdi.com" / "verdibcn" — Cinemes Girona runs on the same admit-one /
  bizcochito cinema platform as Cines Verdi. The JSON-LD does NOT carry the
  screenings (it's venue-level MovieTheater schema), so we parse the DOM cards.

last verified: 2026-06-01
