# Sala Beckett — scraper source map

Last verified against live site: 2026-06-01.

**Venue:** Sala Beckett — Obrador Internacional de Dramatúrgia (Poblenou,
Barcelona). A theatre / performing-arts venue. WordPress + Yoast SEO.
**Categories produced:** `theater` only (the venue programmes theatre, recitals,
readings, talks, festivals — no music concerts in the current programme).

## Source

- **List URLs (two, both scraped):**
  - `https://www.salabeckett.cat/espectacles/` — the shows programme (~27 cards).
  - `https://www.salabeckett.cat/activitats/` — activities: talks, readings,
    festivals, open rehearsals, etc. (~65 cards).
  Both pages render every event on one page (no pagination, no "load more"), and
  use an **identical card structure**, so two requests cover the whole agenda.
- **No event JSON-LD.** The only `script[type="application/ld+json"]` block is
  Yoast SEO boilerplate (`WebPage` + `BreadcrumbList`) — it carries NO event
  date/price/category. So the **rendered DOM cards are the sole source.** (Same
  trap class as Jamboree: don't trust JSON-LD presence; verify it carries the
  fields.)
- WPML `/es/` and `/en/` translations exist per detail page, but capturing them
  needs N extra fetches; we keep only the canonical Catalan title (translations
  intentionally omitted).

## Per-field mapping (within each `.post` card)

| Field | Source |
| --- | --- |
| title | `a.title` text |
| source_url | `a.title` href (normalized: query/fragment/trailing-slash stripped) |
| external_id | the `/espectacle/<slug>` (or `/activitat/`, `/projecte/`) URL segment |
| start_date / end_date | `.dates` text. Single `DD/MM/YYYY` → start only. Range `Del DD/MM/YYYY al DD/MM/YYYY` (or Catalan-elided `De l'DD/MM/YYYY a l'DD/MM/YYYY`) → first token = start, last = end. |
| start_time | the `.mini-wrapper` whose `.mini-title` is `Horari`. **Only for single-day events** (`A les 20 h`, `21:30 h`, `18.30 h`, `18h`, `De 12 h a 1 h`→first). For multi-day runs the Horari is a *weekly schedule* with no single time → start_time None. Non-clock text (`Després de la funció…`) → None. |
| end_time | always None (the site gives no explicit end time). |
| price | the `.mini-wrapper` Preu `.mini-content` text, **verbatim** (e.g. `D'11 € a 22 €`, `10 € \| Personatges de la Beckett 8 €`, `Activitat gratuïta`). Never parsed to a number. |
| image_url | `a.image img` `src`. |
| annotations | `.post-type` label (format) + `.subtitle` (author/byline) + the weekly schedule (for multi-day runs) + `Espai` (room). |
| category | see below. |

## Category discriminator

Sala Beckett is a theatre → **everything maps to `theater`**. The rule keys off
the card's `.post-type` label: if it is a music type (`Concert`/`Música`,
case-insensitive) → `jazz`; otherwise → `theater`. In the current programme no
card is a music type, so all 92 events are `theater`. The post-type vocabulary
(`Espectacle`, `Recital`, `Mostra`, `Xerrada`, `Lectura dramatitzada`, `Festa`,
`Taula rodona`, …) is a too-granular format tag → kept in `annotations`, not as a
top-level category. Title keywords are NOT used (unreliable).

## Verification (2026-06-01)

- `parse_agenda` on the saved fixtures + live `scrape()`: **92 events**.
  Coverage: price **93%**, category **100%**, annotations **100%**,
  start_time **61%** (single-day events; multi-day runs correctly None),
  end_date 27%, image 100%. Categories: `{theater: 92}`.
- Field-by-field browser cross-check of the first 6 espectacles cards: title,
  dates, price, and horari all matched the scraper output exactly. Single-day
  card "El potser com a públic" (15/09/2025, "A les 20 h") → start_time 20:00,
  end_date None, as expected; range cards → end_date set, start_time None,
  schedule stashed in annotations.

## Quirks

- One row per show/activity (no recurrence expansion). A multi-day run is a
  single event with start_date..end_date and the weekly schedule in annotations.
- Catalan date elision: `Del`/`al` vs `De l'`/`a l'` — handled by extracting all
  `DD/MM/YYYY` tokens regardless of connective words.
- Prices are rich free text (ranges, packs, discounts, "Activitat gratuïta").
  Kept verbatim per the free-text price invariant.
- `.activitats` has a few free events with no Preu (price coverage ~91% there).

## Seed requirements

- **venue slug:** `sala-beckett`
- **display name:** `Sala Beckett`
- **address:** `C/ de Pere IV, 228-232, 08005 Barcelona`
- **site_url:** `https://www.salabeckett.cat`
- **category slugs produced:** `theater` (only; `jazz` is reachable in code only
  if a card's post-type is a music type, which does not occur in the current
  programme).
- **list membership:** add to the `theater` cartelera category list, with
  per-venue whitelist category `theater` (`whitelist_category_id = theater`).
  Single-category venue, so a NULL whitelist (all events) is equally fine.
- **note:** the `theater` category and a `theater` list may not yet exist in
  `seed.py` (`CATEGORIES` / lists) — they must be added when integrating.
