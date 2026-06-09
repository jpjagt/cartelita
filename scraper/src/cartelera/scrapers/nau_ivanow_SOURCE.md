# Nau Ivanow — Source Map

**Venue**: Nau Ivanow, C/ de les Hondures 30, 08027 Barcelona (Sant Andreu)  
**Type**: Performing-arts residency space — open activities + professional training  
**Site**: https://nauivanow.com

## Data Source

**WordPress REST API** — custom post type `event`:

```
GET https://nauivanow.com/wp-json/wp/v2/event
  ?per_page=100
  &event_type=12          # or 11 for Formació
  &after=<18-month-ago>
  &orderby=date&order=desc
```

No `_fields` filtering (needed to get `uagb_featured_image_src` when available;
image URL is also extracted from first `<img>` in `content.rendered` as fallback).

## Field Sources

| Field | Source | Notes |
|-------|--------|-------|
| `title` | `title.rendered` (HTML-decoded) | |
| `source_url` | `link` | |
| `slug` | `slug` | Used in external_id |
| `start_date` | First date found in `content.rendered` plain text | Free text: "5 de juny", "4 d'abril" |
| `start_time` | "a les 17h" / "d'11:00h a 12:30" patterns in body | Optional; None if not found |
| `price` | Body text price signals | "gratuït" → "free"; "esgotades" → "sold-out"; "35 €" → "35€" |
| `image_url` | First `<img>` in `content.rendered` | |
| `category_slugs` | Title/body heuristics | "taller familiar" / "en família" / "escola" → `kids`; else `theater` |
| `external_id` | `{slug}@{date}[T{HHMM}]` | Per-occurrence: multi-session workshops each get a separate date-qualified id |
| `annotations` | `["formació"]` for `event_type=11` | |

## Event Types

- `event_type=12` (`actes-oberts`): Open activities — performances, workshops, talks
- `event_type=11` (`formacio`): Professional training workshops (multi-session)

## Date Parsing

Dates are embedded as **free text in the body** (not structured fields).

Patterns recognized:
- `N de MONTH` — e.g. "5 de juny", "21 de febrer"  
- `N d'MONTH` / `N d'MONTH` — e.g. "4 d'abril" (curly U+2019 or straight U+0027)  
- Weekday prefix ignored: "Divendres 5 de juny" → June 5

**Year inference**: Use publication date as anchor. Accept candidate year where
derived date is no more than 30 days before publication; try pub_year, pub_year+1,
pub_year-1 in that order.

**Fallback**: Events with no parseable date use the publication date.

## Multi-Session Workshops

Formació events list multiple session dates in the body as a bullet list:
"Dilluns 5 de maig … Dimarts 6 de maig …"

Each unique date emits a separate `ScrapedEvent`. The external_id is
`{slug}@{date}` (or `{slug}@{date}T{HHMM}` if a start time is found).

## Open Calls Excluded

Events with titles matching `convocatòria oberta` / `obrim convocatòria` /
`convocatoria abierta` are skipped — these are administrative calls for
residency proposals, not public programme events.

## Price Coverage

~88% of events have a parseable price signal (based on 18-month fixture:
22/25 events). The 3 missing-price events are:
- Presentations/talks with no admission fee mentioned (implicitly free but not stated)
- One school-only event with no public ticketing

## Category Mapping

| Trigger | Category |
|---------|----------|
| "taller familiar", "tallers en famil", "per a infants", "extraescolar", "escolars", "per a escoles", "família" in title or first 600 chars of body | `kids` |
| Everything else | `theater` |

Nau Ivanow is a theater/dance residency space; all non-kids events default to
`theater`. A future improvement could add `dance` for clearly movement-based
events, but the current signal (event title) is insufficient without fetching
additional detail pages.

## Lookback Window

`LOOKBACK_DAYS = 548` (~18 months). This covers the site's typical
publication cadence (~1–2 events/month) while keeping fetch time reasonable.

## last verified: 2026-06-09
