# Mercat de les Flors — Source Map

**Venue**: Mercat de les Flors ("Casa de la Dansa"), Plaça de Margarida Xirgu 1, Barcelona  
**Type**: Dance and movement-theater venue  
**Site**: https://mercatflors.cat

## List URL

https://mercatflors.cat/temporada-a-la-vista/

The events list is rendered via JavaScript (MixItUp + WordPress AJAX). The scraper
calls the AJAX endpoint directly:

```
POST https://mercatflors.cat/wp-admin/admin-ajax.php
action=carregar_directori
meta_query[1][key]=temporada_vista, value=1
tax_query[0][taxonomy]=temporada, terms=[8776]
template-part=content-espectacle
```

This returns all events with `temporada_vista=1` (current season, 2025-2026).
The scraper filters client-side to exclude past occurrences (`start_date < today`).

## Card Structure (AJAX HTML response)

```html
<div class="mixitup-main" data-patronbase="{prod_id}">
  <a href="/espectacle/{slug}/">
    <div class="mixitup-img"><img src="..."></div>
    <div class="mixitup-cnt">
      <h2>{artist/company}</h2>
      <h3>{show title}</h3>
      <h4>{date text}</h4>        <!-- Catalan text, e.g. "Del 3 al 5 d'octubre" -->
    </div>
  </a>
  <div class="mixitup-btn">
    <a href="https://es.patronbase.com/...?prod_id={id}&perf_id={id}">COMPRAR ENTRADES</a>
  </div>
</div>
```

## Detail Page Structure

URL pattern: `/espectacle/{slug}/` or `/activitat/{slug}/`

### Per-occurrence dates (`.dte-lst`)

Present when tickets are on sale. Each `<li>` contains:
```html
<a href="https://es.patronbase.com/_MercatFlors/Sections/Choose?prod_id=X&perf_id=Y">
  <h4><span>{day name}, {day} {month abbr}</span> ({HH}:{MM}h)</h4>
</a>
<p class="cancel-alt">Disponible / Esgotat</p>
```

**External ID (when dte-lst available)**: `{prod_id}_{perf_id}`  
**External ID (fallback)**: `{slug}@{YYYY-MM-DD}T{HHMM}`

### Label/Value pairs (`.esp-det-lft` / `.esp-det-rgt`)

| Label       | Content                         | Notes                                      |
|-------------|----------------------------------|--------------------------------------------|
| Temporada   | "2025-2026"                     | Season identifier                          |
| Dies        | Text date or `.dte-lst` items   | Per-occurrence dates when tickets live     |
| Durada      | "55 minuts"                     | Not scraped                               |
| Tarifa      | "8 €" (in `.desk-para`)         | Main public price                          |
| Horari      | "20 h", "20.30 h"               | Fallback time when no `.dte-lst`           |
| Espai       | "Sala MAC", "Sala PB"           | Not scraped                               |

**DIVENDRES JOVE** (Young Fridays discount) appears as a separate label/value pair.
It is ignored; only the "Tarifa" field is used for price.

## Price Convention

- Main "Tarifa" field from `.desk-para` or plain `<p>` text in `.esp-det-rgt`
- Accessibility tier (0 €) is filtered out → "free" only if all prices are 0
- "Gratuït" → "free"; "Exhaurit" → "sold-out"
- Multiple tiers: take lo and hi, apply `format_eur_range(lo, hi)` (range only when hi >= 2×lo)
- DIVENDRES JOVE and other discount tiers are ignored

## Category Mapping

- **`dance`**: all events (the venue is "Casa de la Dansa")
- **`kids`**: added when title or URL contains "elPetit", "funcions escolars", or "familiar"

## Date Parsing (Catalan text)

Patterns handled:
- `"13 de juny"` → single date
- `"Del 3 al 5 d'octubre"` → range
- `"Del 2 al 5 i 11 i 12 d'octubre"` → range + extra days
- `"17 i 18 d'octubre"` → same-month two days
- `"31 d'octubre i 1 de novembre"` → cross-month pair
- `"28 de setembre"` → single date

Year is inferred: if month > current month → current year, else next year.
(Works for near-future events; events 12+ months away may need revisiting.)

## External ID

Per-occurrence key:
- When `.dte-lst` has Patronbase link: `{prod_id}_{perf_id}`
- Otherwise: `{url-slug}@{YYYY-MM-DD}T{HHMM}`

## Data Quality Notes

- The AJAX endpoint returns all season events (past + future). Client-side filter
  removes occurrences where `start_date < today`.
- Events without tickets yet ("funcions escolars", future shows) don't have
  `.dte-lst`; dates come from the list page's `<h4>` text.
- Some future events have no "Dies" field at all in the detail page; fallback to
  list page date text.
- "Horari" on detail page is the scheduled time; used as fallback start_time.

## Last Verified

2026-06-09 — 139 events (79 shows × avg 1.8 occurrences), 100% price coverage,
100% time coverage. Cross-checked first 6 events against live browser: titles,
dates, times, and prices match.
