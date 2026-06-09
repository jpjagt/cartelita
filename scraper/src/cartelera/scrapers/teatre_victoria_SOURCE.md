# Teatre Victòria — Source Map

**Venue**: Teatre Victòria, Av. del Paral·lel, 67-69, 08004 Barcelona  
**Site**: https://www.teatrevictoria.com

## List URL

```
https://www.teatrevictoria.com/ca/cartellera.html
```

Used only to discover the set of current show detail-page URLs via
`[role=listitem] a.titol[href]`. The show numeric ID is extracted from the
`id_NNN` CSS class on each `[role=listitem]` element.

## Data source: JSON-LD Event list (detail pages)

Each show's detail page embeds three `<script type="application/ld+json">` blocks.
The **second** block is a JSON array of `@type: "Event"` objects — one per
performance occurrence. This block carries every field we need.

Fields per `Event` object:

| Field | JSON-LD path |
|-------|-------------|
| `title` | `name` |
| `start_date` | `startDate` (ISO-8601, e.g. `"2026-10-14T20:30:00+02:00"`) |
| `start_time` | parsed from `startDate`'s time component |
| `source_url` | `url` |
| `image_url` | `image` (HTML entity-unescape `&amp;` → `&`) |
| `price` | `offers.price` (float euros) + `offers.availability` |

The third block is a `Product` list — a near-duplicate; ignored.

## Price convention

- `offers.availability == "https://schema.org/SoldOut"` → `"sold-out"`
- `offers.price == 0` → `"free"`
- `offers.price > 0` → `"{round(price)}€"` (single-tier flat price; no
  priceSpecification range is used since minPrice == maxPrice for this venue)

## Category mapping

All shows → `theater`. Teatre Victòria is a large-format theatre on the
Paral·lel that stages musicals, magic shows, and comedy monologues. No other
Cartelera categories apply.

## external_id

`"{show_id}@{YYYY-MM-DD}T{HHMM}"` — the show's numeric ID (from `id_NNN` CSS
class on the listing card) qualified with date and time to give one row per
occurrence. Example: `"332@2026-10-14T2030"`.

Without the date+time qualifier, multiple sessions of the same show would collapse
to a single DB row on upsert.

## Quirks

- The venue is currently running only 2 shows (Temporada 25/26). The scraper
  discovers shows dynamically, so it will pick up new shows automatically.
- Juan Dávila / El Palacio del Pecado (show 330): all 6 sessions are SoldOut.
- El Mago Pop (show 332): 47 sessions Oct–Dec 2026, mostly InStock at 42€.

## Last verified

2026-06-09 — live JSON-LD matches fixture field by field (title, startDate, price,
availability). Scraper output: 53 events, 100% price/category/time/image coverage.
