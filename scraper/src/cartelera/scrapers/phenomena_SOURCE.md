# Sala Phenomena Experience — source map

Venue slug: `phenomena`. Single-screen repertory cinema in Barcelona. Single
category: **film** (every session is a film screening; the venue does not
sub-categorize, though films are grouped into thematic *ciclos*).

## List URL(s)

- Full programme (cartelera): `https://phenomena-experience.com/index?pag=cartelera`
  - Server-rendered HTML (no JS needed). One `div.cartelera` per **film**, each
    with all its upcoming session dates/times. This single page is the complete
    schedule (no need to walk per-day or per-week pages).
  - NOTE: the brief's `/programacion/` and the homepage `pag=programacion` are NOT
    the full listing (homepage redirect / highlights only). `pag=cartelera` is the
    real listing. There is no `/programacion/` path (404).

## Data source (server-rendered HTML)

One `div.cartelera` per film. Per film:

| Field        | Source                                                                   |
|--------------|--------------------------------------------------------------------------|
| `title`      | first `.cartelera-titulo .ver-ficha` text (e.g. "A.I. INTELIGENCIA ARTIFICIAL (VOSE)") |
| `source_url` | `.cartelera-imagen a[href*=ficha]` → `…/index?pag=ficha&evento=<N>`       |
| `image_url`  | `.cartelera-imagen img[src]` (already absolute)                           |
| `description`| original/alt title = second `.cartelera-titulo .ver-ficha`; plus the runtime/director/cast lines in `.cartelera-informacion` |
| annotations  | the **ciclo** from `.cartelera-titulo-ciclo span` ("Ciclo: SPIELBERG FANTÁSTICO" → "SPIELBERG FANTÁSTICO"); ~half the films belong to one |
| sessions     | `.lista-sesiones` holds `.fch-format` (a **date**) immediately followed by a sibling `.sesiones-dia`; each `.grupo[id-ses]` inside is one **session** with its time in the child `<div>` ("15:15h") |

### One ScrapedEvent per OCCURRENCE (session), not per film

A film screens on several dates/times. We emit one `ScrapedEvent` per `.grupo`
session:

- `start_date`: parsed `dd/mm/yyyy` from the `.fch-format` **text** (the `format`
  attribute is just a JS display template — ignore it; read the text).
- `start_time`: `HH:MM` from the `.grupo > div` text ("15:15h").
- `external_id`: the session's `id-ses` attribute (e.g. `"13204"`). This is unique
  **per occurrence** (verified 54/54 unique in the fixture), so unlike a film slug
  it does NOT collapse occurrences — it is the venue's native per-session id. (The
  Filmoteca trap does not bite here because `id-ses` is already per-session; we
  still assert per-occurrence uniqueness in the tests.)
- `category_slugs`: always `["film"]`.

## Price

The listing carries **no price**. Each film's price lives on its **ficha detail
page** (`pag=ficha&evento=<N>`) in a single `.precio` element (e.g. `"9€"`).
Price varies per film (observed 9€ / 12€ / 14€ / 15€), so it is NOT a flat venue
rate — the scraper fetches each film's ficha once and applies that price to all of
that film's sessions. Output is the concise display string (e.g. `"9€"`); on
fetch/parse failure price falls back to `None` (best-effort).

`Gratuita` / sold-out: the listing's embedded session JSON (`addToJSON('s', …)`)
has a `Gratuita` flag and availability fields, but in the current programme none
are free or sold out, so the scraper does not special-case them (the per-film
ficha `.precio` is the source of truth). If free screenings appear later, the
ficha `.precio` is expected to render "Gratis"/"0€" and should be normalized then.

## i18n

The site is Spanish-only for the schedule. The original-language film title (2nd
`.ver-ficha`) is kept in the description. No translations emitted.

## Quirks

- The listing emits each session's `addToJSON('s', …)` and `addToJSON('f', …)`
  script blocks (sometimes duplicated). We DO NOT parse those — they carry no
  price and the date/time are already in the rendered DOM. We read `.fch-format` +
  `.grupo` instead.
- `.fch-format` and `.sesiones-dia` are **siblings** (paired in document order),
  not parent/child. Pair each `.fch-format` with its next `.sesiones-dia` sibling.
- httpx default request works (no special User-Agent needed). browser-use headless
  was blocked by the site (ERR_HTTP_RESPONSE_CODE_FAILURE / ERR_ABORTED); recon and
  verification were done via httpx + the saved fixture instead.

last verified: 2026-06-01
