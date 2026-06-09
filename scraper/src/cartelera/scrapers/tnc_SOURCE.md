# TNC (Teatre Nacional de Catalunya) — Source Map

**Site:** https://www.tnc.cat  
**Stack:** Drupal (no JSON-LD, no `__NEXT_DATA__`)  
**Last verified:** 2026-06-09

## List URLs

Two season list pages are scraped:
- `https://www.tnc.cat/ca/temporada-2025-2026` — current season
- `https://www.tnc.cat/ca/temporada-2026-2027` — upcoming season

## Data source

DOM cards — one `<article data-history-node-id="…">` per show.

| Field | Selector / Source |
|-------|-------------------|
| node_id (external_id) | `article[data-history-node-id]` attribute |
| title | `article h3 a, article h2 a` — `.get_text(strip=True)` |
| detail URL | `article h3 a[href]` → prepend `https://www.tnc.cat` if relative |
| date range | `.field--name-field-date-range` — text `"DD/MM/YYYY al DD/MM/YYYY"` |
| sala | `.container-teaser--tags .field__item` |
| status badge | `.card-container-status` — text ("Exhaurit", "Últimes entrades!", "Premi Max", …) |
| image | first `<img>` in article |
| **price** | **detail page only**: `.field-espectacle--preus` — text `"De X € a Y €"` |

## Price

Price lives **only** on the individual show detail page (`/ca/<show-slug>`).  
`scrape()` fetches each show's detail page in the same `httpx.Client` session.

Format: `"De 14 € a 28 €"` → parsed with regex, formatted via `format_eur_range(lo, hi)`.  
- `hi >= 2*lo` → range string `"14–28€"`
- `hi < 2*lo` → single value `"{hi}€"`
- "gratuït / gratuïta" → `"free"`
- "properament" (TBA) → `None`

Status `"Exhaurit"` overrides any price to `"sold-out"`.

## Category

All TNC shows → `theater` (TNC is a theater-only venue; no music, film, etc.).

## external_id

`data-history-node-id` attribute on each `<article>`. This is a per-production node ID, not per-screening; it uniquely identifies one show run. TNC presents shows as date ranges (not individual sessions), so no date-qualification needed.

## Filtering

Shows with CSS class `.card-status--finalitzat` on the status badge are skipped (season is over / show has ended).

## Quirks

- Some future shows have "Preus i posada a la venda properament" (prices coming soon) → `price = None`
- The sala (venue space: "Sala Gran", "Sala Petita", "Sala Tallers", etc.) is stored as an annotation
- Both current-season page and next-season page are scraped; shows that appear on both are deduped by `node_id`
