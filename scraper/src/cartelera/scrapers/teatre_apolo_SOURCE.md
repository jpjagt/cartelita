# Teatre Apolo — Source Map

## Venue
Avinguda del Paral·lel, 59, 08004 Barcelona  
Historic ~900-seat venue (1904) with broad programming: musicals, dance, concerts, comedy, magic, children's shows.

## Data source
**DOM scraping** — the WordPress/Elementor-built site has JSON-LD (Yoast SEO boilerplate only: WebPage/Article/BreadcrumbList) that carries NO price, date, or category. All fields are read from rendered DOM.

## List URL
`https://teatreapolo.com/cartelera/`

One `article.elementor-post` card per active show (no pagination; typically 25–35 shows).

## Field mapping (list page)

| Field | Source | Notes |
|---|---|---|
| title | `h2.elementor-heading-title` (or `h3`) — text | One per card |
| source_url | `h2.elementor-heading-title a[href]` | Absolute URL |
| start_date / end_date | `.elementor-widget-text-editor .elementor-widget-container` — first non-empty text | Spanish date string; see Date formats below |
| category_slugs | WordPress CSS classes on `article` (`category-musical`, `category-danza`, etc.) | See Category mapping |
| image_url | First `<img>` in the card | WordPress thumbnail |
| external_id | Last path segment of `source_url` (URL slug) | Stable per show engagement |
| annotations | `.elementor-button-text` badge text | e.g. "MUSICAL", "DANSA", "CONCERT" |
| price | **Not on list page** — fetched from detail page | See Detail page below |

## Detail page (price enrichment)

URL: each show's `source_url` (e.g. `https://teatreapolo.com/cartelera/tarzan-el-musical/`)

Price selector: `.elementor-widget-text-editor .elementor-widget-container` containing `"Mejor Precio XX€"`.  
Pattern: `Mejor Precio (\d+)€` → normalized to `"XX€"`.  
Free events: "Entrada gratuita" → `"free"`.  
Sold-out: "Sold Out" → `"sold-out"`.

Price coverage: **100%** (all shows have "Mejor Precio" on their detail page as of last verification).

## Date formats (Spanish)

All formats observed in the live fixture:
- `Del D al D de Month de YYYY` — same-month range
- `Del D de Month al D de Month de YYYY` — cross-month range (year at end)
- `Del D de Month de YYYY al D de Month de YYYY` — cross-month range (year both)
- `D de Month de YYYY a D de Month de YYYY` — range (alternative connector)
- `D y D de Month de YYYY` — two performance dates (same month), treated as range
- `D de Month y D de Month de YYYY` — two dates (different months), treated as range
- `[Weekday] D de Month de YYYY` — single date
- `D de Month de YYYY` — single date

## Category mapping

| WordPress class | Our slug | Notes |
|---|---|---|
| `category-musical` | `theater` | Musical theatre |
| `category-danza` | `dance` | Ballet, contemporary, folk dance |
| `category-danza` + flamenco in title | `dance` + `flamenco` | e.g. "Luna, Cía flamenca Rocío Pozo" |
| `category-concierto` | `pop` | Tribute bands, film-music concerts, pop/rock shows |
| `category-comedia` | `theater` | Comedy theatre |
| `category-drama-clasico` | `theater` | Classical drama |
| `category-varios-estilos` | `theater` | Magic shows, variety; default catch-all |
| `category-infantil` | `kids` | Children's shows |

Events may carry multiple WordPress categories (e.g. `category-infantil category-musical`) → both slugs are emitted.

## external_id
URL slug (last path segment): e.g. `tarzan-el-musical`.  
Each show is one engagement at the venue; the slug is unique per run. No per-occurrence qualification needed (one `ScrapedEvent` per show, not per performance night).

## HTTP requirement
The server rejects requests without a browser-like User-Agent (returns an empty response). A `Mozilla/5.0 ...` User-Agent header is required.

## Calendar widget (not used)
The site embeds a SimCalendar (calendar ID 755) on both the `/calendario/` page and each show's detail page, accessible via WordPress admin-ajax.php with action `simcal_default_calendar_draw_grid`. This calendar shows individual performance occurrences (date + time) for all shows, but is paginated by month. Since each show is scraped as one engagement (not per-occurrence), we don't use the calendar API.

## Last verified
2026-06-09
