# Teatre Lliure — Source Map

## Venue
Teatre Lliure is Barcelona's main publicly-funded theatre, with two buildings:
- **Lliure de Montjuïc** — Pg. de Santa Madrona, 40-46 (main Sala Fabià Puigserver + Espai Lliure)
- **Lliure de Gràcia** — C/ de Montseny, 47

## List URL
`https://www.teatrelliure.com/ca/temporada-25-26`

Single page, no pagination. All 40–45 shows for the season are rendered in a
`<ul id="ShowList">` (one `<li>` per show). The filter dropdown is by venue room
(Sala Fabià Puigserver / Gràcia / Espai Lliure) only — no category filter.

## Data Source
**DOM scraping.** No JSON-LD, `__NEXT_DATA__`, or embedded JSON on either page.

### List-page fields (one `<li class="filter-show-*">` per show)
| Field       | Selector                         | Notes                              |
|-------------|----------------------------------|------------------------------------|
| title       | `h3.tit a`                       | text content                       |
| detail URL  | `h3.tit a[href]`                 | `/ca/<slug>` relative path         |
| slug        | last path segment of detail URL  | used as `external_id`              |
| period      | `dd.outcome` [0]                 | various date formats (see below)   |
| room        | `dd.outcome` [1]                 | e.g. "Montjuïc. Sala Fabià Puigserver" |
| image       | `figure.pic-pill img[src]`       | `//domain/images/...` (add `https:`) |
| description | `p.desc`                         | crew credits / subtitle            |

### Detail-page fields (`.item-set` blocks, each with `<h3>` label + `<p>` value)
| Label              | Used for                                                    |
|--------------------|-------------------------------------------------------------|
| `Preu`             | price string (see Price section below)                      |
| `Horari`           | schedule text → annotation                                  |
| `Edat recomanada`  | age recommendation → annotation; triggers `kids` if present |

## Date Formats
The period text uses at least six distinct formats:
1. `DD/MM/YY` — single date (2-digit year)
2. `DD/MM/YYYY` — single date (4-digit year)
3. `DD/MM — DD/MM/YY` — range (em-dash; first date has no year)
4. `DD/MM - DD/MM/YY` — range (hyphen)
5. `D, D, D i D/MM/YY` — multi-date list (only the last token has month/year)
6. `DD/MM` — bare day/month with no year → **skipped** (cannot determine year)

Parser strategy: extract the last `DD/MM/YY(YY)` token as the end date, then
infer the start from the first day-number(s) that precede it.

## Price
Source: detail-page `.item-set[h3="Preu"] p`.
Not available on the list page; scraper fetches each detail URL.

- `"De X a Y €"` → `format_eur_range(X, Y)` (range when Y ≥ 2×X)
- `"Gratuït"` / `"Gratuït amb reserva prèvia"` → `"free"`
- Single `"N €"` → `"N€"`

## Category Mapping
Teatre Lliure is a performing-arts venue. Default: `theater`.

`kids` exception: a show is classified as `kids` when its detail URL slug
contains `elpetit` (the festival slug suffix), OR when the detail page carries
an `Edat recomanada` field matching `De N a M anys`.

No explicit flamenco/dance discriminator exists on the site. Shows like
"Calentamiento" (Rocío Molina) are produced within the main theater programme
and are classified `theater`; Teatre Lliure membership in the `theater` list is
the appropriate placement.

## External ID
The URL slug (last path segment of the detail link). Each list-page entry is a
unique production run — not one row per night — so no date qualification is
needed.

## Skipped shows
Shows whose date string has no year component (e.g. `01/07 - 31/07` for the
Grec festival page; `05/10` for a single outdoor event) are skipped because
the canonical year cannot be inferred from the page.

## Last verified
2026-06-09
