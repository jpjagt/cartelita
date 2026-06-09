# Teatre Romea — Source Map

## List URL
`https://www.teatreromea.cat/ca/season/` — current season, 3 shows per page (no pagination).

## Data source
DOM scraping only. The `application/ld+json` block contains only Yoast SEO boilerplate (WebPage/BreadcrumbList) — no event dates, price, or category.

## Season page selectors

| Field        | Selector / attribute                                      |
|--------------|-----------------------------------------------------------|
| Show cards   | `.espectacle-query__item`                                 |
| Title        | `.title a` (text)                                         |
| Detail URL   | `a.image-container[href]`                                 |
| Poster image | `img[src]` (first img in card)                            |
| Category     | article CSS class: `dis_11`→theater, `dis_7`→theater, `dis_17`→theater, `dis_4`→kids |

## Show detail page selectors

| Field        | Selector / attribute                                      |
|--------------|-----------------------------------------------------------|
| Sessions     | `.espectacle_side .espectacle_funciones li` (sidebar only — also appears in hidden modal, use sidebar to avoid duplicates) |
| Date + time  | `.date` (text), e.g. "dimecres, 10/06/2026 - 20:00"      |
| "Other dates"| `li.other_dates` — skip (no `.date` span, links to ticketing site) |

## Category mapping

Filter buttons on season page map CSS classes to genres:
- `dis_11` = Teatre → `theater`
- `dis_7` = Comèdia → `theater` (comedy is a sub-genre)
- `dis_17` = Tragicomèdia → `theater`
- `dis_4` = Familiar → `kids`

Genre label (Comèdia, Tragicomèdia, Familiar) is added as a free-form annotation.

## external_id
`{show-slug}@{YYYY-MM-DD}T{HHMM}` — per-occurrence. Show slug from URL path `/ca/ex/<slug>/`.

## Price
Not available on teatreromea.cat. The site only shows a generic discount policy (15% off for seniors, families, etc.) but no actual ticket prices. `price = None` for all events.

## Quirks
- Sidebar `espectacle_funciones` shows the next ~6 upcoming sessions; additional sessions are behind a "Per a altres dates" link to the ticketing platform. The scraper captures what's visible without following the external link.
- When the show is near its end, all remaining sessions fit in the sidebar (no "altres dates" item).

## Last verified
2026-06-09 — scraper output cross-checked against live site session lists, field by field. Show 1 (Una madre de película): 6 sessions exact match. Show 2 (El retrat de Dorian Gray): 6 sessions + "altres dates" item correctly skipped.
