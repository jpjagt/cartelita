# Teatre Poliorama — Source Map

**Venue:** Teatre Poliorama, La Rambla 115, Barcelona  
**Site:** https://www.teatrepoliorama.com  
**Last verified:** 2026-06-09

## Scraping Strategy

Two-step approach: agenda page → show URLs → detail page JSON-LD per occurrence.

### Step 1: Agenda page

**URL:** `https://www.teatrepoliorama.com/ca/programacio.html`

Renders `.contenidor-product` cards (no pagination — all shows in one page).

| Field | Selector |
|-------|----------|
| Detail URL | `a.imatge[href]` |
| Category label | `.categoria` text |

The agenda page shows 14 shows (as of 2026-06-09) across all categories.
Category labels on the card:
- `"Flamenco"` → `flamenco`
- `"Petit Poliorama"` → `kids`
- `"Nits del Polio"` → `theater`
- `"TEMPORADA 2025/26"` / `"TEMPORADA 2026/27"` → `theater` (season label only, no genre)

### Step 2: Detail pages

**URL pattern:** `/ca/programacio/c/{id}-{slug}.html`

Each detail page embeds multiple `<script type="application/ld+json">` blocks,
one per occurrence (`@type: Event`). These carry full per-session data.

| Field | JSON-LD path |
|-------|-------------|
| title | `name` |
| start_date + start_time | `startDate` (ISO 8601 with TZ offset) |
| price | `offers.price` (float, EUR) |
| availability | `offers.availability` (schema.org URL) |
| image_url | `image` |
| description | `description` (may contain HTML tags, stripped) |

**Availability values:**
- `https://schema.org/InStock` → normal price
- `https://schema.org/SoldOut` / `https://schema.org/OutOfStock` → `"sold-out"`
- price == 0 → `"free"`

### external_id

`{show-slug}@{YYYY-MM-DD}T{HHMM}` — the show slug (e.g. `875-michaels-legacy`)
qualified with the occurrence date and time. This ensures two sessions on the
same day (e.g. 17:00 and 20:00) produce different external_ids.

## Coverage (2026-06-09)

- 14 shows scraped from agenda page
- 463 total occurrences across all shows
- **Price coverage: 100%** (463/463) — JSON-LD carries price for every occurrence
- **Image coverage: 100%** (463/463)
- **Category breakdown:** theater: 255, flamenco: 176, kids: 32

## Caveats

- Gran Gala Flamenco is a permanent resident show with hundreds of past/future
  dates — all are scraped (dating back to 2021). The upsert will update existing
  rows idempotently.
- Category classification for "TEMPORADA" shows defaults to `theater`. Shows like
  Michael's Legacy (MJ tribute) or Coldday (Coldplay tribute) are pop concerts
  but are not labeled as such on the site — they're filed under theater.
- The site paginates the session list in the UI (only 5 shown at once), but the
  JSON-LD contains all occurrences on the page load. We rely on JSON-LD, not DOM
  session rows.
