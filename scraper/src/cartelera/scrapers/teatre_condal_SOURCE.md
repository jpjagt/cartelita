# Teatre Condal — Source Map

**Venue:** Teatre Condal, Carrer de la Creu dels Molers 7, Barcelona (Paral·lel district, founded 1903)
**Site:** https://www.teatrecondal.cat

## List URL

```
https://www.teatrecondal.cat/ca/season/
```

WordPress site. No JSON-LD event data (only Yoast SEO boilerplate WebPage/BreadcrumbList).
All data comes from DOM parsing.

## Data source

### Season page (`/ca/season/`)

Selector: `article.espectacle-query__item`

| Field       | Selector                         | Notes |
|-------------|----------------------------------|-------|
| title       | `.title a` (text)                | |
| source_url  | `.title a[href]`                 | |
| image_url   | `img[src]`                       | |
| category    | article CSS class `dis_N`        | see mapping below |

### Detail page (`/ca/ex/<slug>/`)

Selector: `ul.espectacle_funciones li:not(.other_dates)`

| Field       | Selector / Source                | Notes |
|-------------|----------------------------------|-------|
| start_date  | `.date` text — `DD/MM/YYYY`      | Catalan day-of-week prefix; regex extracts date |
| start_time  | `.date` text — `HH:MM`           | Always present alongside date |
| external_id | `a[href]` → `/select/<ID>`       | oneboxtds per-session integer ID |
| price       | not available                    | external ticketing only → `None` |

## Category mapping

| `dis_N` | Venue label   | Cartelera category |
|---------|---------------|--------------------|
| dis_1   | Musical       | theater            |
| dis_2   | Dansa / Ballet| dance              |
| dis_7   | Comèdia       | theater            |
| dis_8   | Concert       | theater (choral)   |
| dis_11  | Teatre        | theater            |
| dis_12  | Monòlegs      | theater            |
| dis_17  | Tragicomèdia  | theater            |

Default for unknown `dis_N`: `theater`.

## external_id

Format: `"teatre-condal:<oneboxtds_session_id>"`  
Example: `"teatre-condal:2833917"`

The oneboxtds `/select/<ID>` integer is unique per session (verified: two sessions
on the same date at different times have different IDs). Falls back to
`"<slug>@<date>T<HHMM>"` if no purchase link found.

## Skipped items

`ABONAMENT KULUNKA` — a subscription bundle, not a performance. Its sessions have
no `.date` span (only bundle-name text), so they are silently skipped by the
`li:not(.other_dates)` + date-span check.

## Price

Price is not available on the venue website. Ticket prices are only shown on
the external `tickets.oneboxtds.com` platform. All events have `price=None`.

## Season structure

Teatre Condal lists a season programme (~10 shows for 2025/26 season). Each show
runs for several days/weeks. The detail page lists the next ~6 upcoming sessions
plus a "For other dates" link to the full ticket platform.

## Last verified

2026-06-09 — 10 shows on season page, all have sessions on detail pages.
- L'auca del Sr. Pera: 6+ sessions (dis_11 → theater)
- BARCELONA GAY MEN'S CHORUS-SHAMPOO: sessions (dis_8 → theater)
- Carmen (Ballet de Barcelona): 4 sessions (dis_2 → dance)
- ANDRÉ Y DORINE: sessions (dis_11 → theater)
- ABONAMENT KULUNKA: SKIPPED (bundle, no dates)
- SOLITUDES: sessions (dis_11 → theater)
- Forever: sessions (dis_11 → theater)
- 53 DOMINGOS: sessions (dis_11 → theater)
- ELLA ERA ANITA: 1 session (dis_1 → theater)
- Germans de Sang: 6 sessions (dis_1 → theater)
