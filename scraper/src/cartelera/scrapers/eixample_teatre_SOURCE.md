# Eixample Teatre — Source Map

Venue: Eixample Teatre, C/ del Consell de Cent, 425, Barcelona  
Site: https://www.eixampleteatre.cat  
Speciality: Comedy, musicals, family shows

## Data flow

1. **Fetch programme list** `GET /ca/programacio`  
   Parses one HTML grid page — no API or JSON-LD.  
   Returns all active shows as `.col-md-3.col-sm-6` cards.
   Cards contain: title, detail href, image URL, price text, short description.
   **Dates are NOT on the list page** — only on each show's detail page.

2. **Fetch each detail page** `GET /ca/<show-slug>`  
   The sessions section (if present) is a `<ul class="programacion">` with one
   `<li>` per occurrence. Each row has five `div.col-*` children:
   - col 0 → weekday (text, e.g. "Divendres")
   - col 1 → date DD/MM/YYYY
   - col 2 → time "HH:MM h"
   - col 3 → public price e.g. "20€"
   - col 4 → club price e.g. "Club 18€" (discounted — ignored)
   
   Shows without a `<ul class="programacion">` have no confirmed dates yet
   ("Pròximament") and are skipped (no ScrapedEvent emitted).

## Field mapping

| ScrapedEvent field | Source |
|---|---|
| `title` | `h1` text on detail page |
| `start_date` | col 1 in `ul.programacion li`, parsed as DD/MM/YYYY |
| `start_time` | col 2, pattern `HH:MM h` |
| `source_url` | `https://www.eixampleteatre.cat` + detail href from list page |
| `category_slugs` | Venue category tags in `.fondo-auxiliares a[href*="id_estilo"]`; mapped to known slugs (see below) |
| `price` | col 3, e.g. "20€". "Agotado"/"sold out" → "sold-out". None if absent. |
| `image_url` | `#main-ctn img.img-fluid` (the main show image on detail page) |
| `external_id` | `<slug>@<YYYYMMDD>T<HHMM>` (per-occurrence, derived from detail href + date + time) |
| `annotations` | Venue category labels too granular for top-level (e.g. "Humor", "Monòlegs", "Màgia") |
| `description` | None (description text exists on detail page but is too long / HTML-heavy) |

## Category mapping

Venue tags → Cartelera categories:

| Eixample tag | Cartelera slug |
|---|---|
| Comèdia / Comedia | `theater` |
| Teatre / Teatro | `theater` |
| Familiar | `kids` |
| Humor | (annotation only) |
| Màgia / Magia | (annotation only) |
| Monòlegs | (annotation only) |

Default fallback: `theater` (venue is a comedy/theatre venue — all content is theatrical).

## external_id

Format: `{slug}@{YYYYMMDD}T{HHMM}`  
Example: `bonobos@20260612T2030`

The slug is extracted from the detail page URL (e.g. `/ca/Bonobos` → `Bonobos`).
This ensures each screening occurrence gets a unique key even when a show runs
multiple times per day (e.g. Bonobos has 16:00 and 20:30 on the same Saturday).

## Price convention

- Public price from col 3 of the session row is used directly (e.g. `"20€"`).
- Club price (col 4, always lower) is ignored — we show the public price.
- "Des de X€" text on the list page / sidebar is NOT used — it's approximate.
- No free events observed; no sold-out indicator found in the DOM (button stays "Comprar").
- If a session button says "Agotado" (text of `.btn`) → `"sold-out"`.

## Quirks

- The list page has ~16 shows; typically only 2–4 have confirmed sessions. The
  rest are "Pròximament" (coming soon) with no dates, so they produce no events.
- "Regala EIXAMPLE TEATRE" (gift card page) appears in the card list — filtered
  out because it has no sessions and its detail page has no `ul.programacion`.
- Some shows have multiple sessions per day — each emits a separate ScrapedEvent.
- The language version `/ca/` is Catalan; `/es/` is Spanish. We use `/ca/` for
  canonical URLs and category labels.

## last verified: 2026-06-09
