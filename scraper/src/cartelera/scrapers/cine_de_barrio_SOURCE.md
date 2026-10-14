# Cine de Barrio — source map

Venue slug: `cine-de-barrio` (Asunción). Single category: **film** — a 20-seat
auteur cinema in Barrio Las Mercedes (Defensa Nacional 737 casi Washington).
Member of Asunción's `film` list (whitelist `film`).

Own site: `https://cinedebarrio.com` — a **Framer** site, fully server-rendered
(httpx with the Cartelita browser UA; no bot protection). Framer renders the
page once per breakpoint, so every field appears 2–3× in the HTML: dedupe.

## List URL

- `/eventos` — one card per film currently programmed:
  `a[href^="./eventos/<slug>"]` with `[data-framer-name="Titulo"]`,
  `[data-framer-name="Genero"]` (often empty; e.g. "Terror") and the poster
  `img[src]` (framerusercontent.com). Non-ASCII slugs (`el-príncipe-de-nanawa`)
  are percent-encoded to match the page's own `og:url`.

## Detail page (`/eventos/<slug>`) — one row per screening

| Field | Source |
|---|---|
| `title` | `[data-framer-name="info"] [data-framer-name="Titulo"]` |
| `description` | `[data-framer-name="Descripcion"]` |
| `start_date`/`start_time` | each `[data-framer-name="Fecha y Hora"] time[datetime]` ("2026-10-14T21:10:00.000Z"). **The "Z" is not UTC**: Framer stores the wall-clock showtime; the rendered text ("14 oct 2026, 21:10") is the same clock time, so it is read as local Asunción time. |
| `price` | per showtime card (the `[data-border="true"]` ancestor of the date): `[data-framer-name="Precio"]` "40.000 PYG" → `pyg_price` → `"40.000₲"`; free screenings have no Precio but a note in the card's `section` ("Entrada libre y gratuita. Por orden de llegada…") → `"free"`; "agotad…" → `"sold-out"`. Scoped to the card so a card without a price never borrows the next one's. |
| `external_id` | the card's Tally ticket link `https://tally.so/r/…?screening_id=rec…` → the screening's Airtable record id (per occurrence). Free screenings have no ticket link → `<slug>@YYYY-MM-DDTHHMM`. |
| `image_url` | the list card's poster |
| `annotations` | the list card's Genero label, when set |
| `language` | not stated → None |

No exclusions: the site only lists screenings (room rental lives on a
separate `/alquilá-la-sala` page, not in `/eventos`). The "Asientos
Disponibles" count is filled client-side and not read.

## Verification

Last verified: **2026-10-14 via HTTP cross-check.** Live scrape: 17 screenings
of 9 films, 2026-10-14 → 2026-10-31; coverage: time 17/17, price 17/17
(14× `40.000₲`, 3× `free`), image 17/17, description 17/17. Independent check:
regexed every detail page's raw `<time datetime>` + the following
`… PYG`/"libre y gratuit" text — all 17 (title, date, time, price) tuples
identical to the scraper's (0 mismatches). Cold-start DB per-day counts match.
