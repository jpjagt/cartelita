# Balañá Group Theaters — Source Map

## Venues covered

| Venue | Slug | theater_id |
|---|---|---|
| Teatre Tívoli | `teatre-tivoli` | 3 |
| Teatre Coliseum | `teatre-coliseum` | 2 |
| Teatre Borràs | `teatre-borras` | 4 |
| Paral·lel 62 | `paralel-62` | — (stub, see below) |

## Data source

**Site**: https://www.balanaenviu.com

**API endpoint**: `POST https://www.balanaenviu.com/webapi/shows-filter`

The site is a Laravel application. Show listings are loaded client-side via an
AJAX POST to `/webapi/shows-filter`.  The endpoint requires an active session
cookie and a CSRF token (obtained by GETting the venue page first).

Request body fields:
- `_token` — CSRF token from `<meta name="csrf-token">` of the venue page
- `theater` — internal theater ID (integer string)
- `search`, `startDate`, `endDate` — empty for all shows
- `page` — 1 (returns all shows, hasMore=false)
- `section` — "Theater"

Response JSON keys:
- `shows.data` — array of show objects (JSON)
- `html` — pre-rendered listing HTML blob
- `hasMore` — bool

## Fields per show (from `shows.data`)

| Field | Source |
|---|---|
| `title` | `show.title.ca` (or `.es`) |
| `slug` | `show.slug.ca` (or `.es`) — used to build `source_url` |
| `source_url` | `https://www.balanaenviu.com/espectaculo/{slug}` |
| `start_date` | `show.start_date` (ISO datetime string, first occurrence) |
| `end_date` | `show.end_date` (last occurrence) |
| `genre` | `show.genre` — `{id, name: {ca}}` |
| `image_url` | `show.thumbnail_image` (S3 URL or path) |
| `description` | `show.description.ca` (HTML, stripped of tags) |
| `price` | **NOT AVAILABLE** — not in API, not on detail pages |
| `cancelled` / `sold-out` | `.customLabel` text in listing HTML blob |

## Multi-session expansion

When a show spans multiple days (`start_date ≠ end_date`), its detail page
(`/espectaculo/{slug}`) contains `.ticketsBox__content--item` elements, each
with month/day/hour.  We fetch the detail page and emit one `ScrapedEvent` per
session.  For single-day shows we use the API date/time directly.

## external_id

Per-occurrence: `balana-{slug}@{YYYY-MM-DD}T{HHMM}`.

This is derived from the slug + session datetime, ensuring uniqueness even
when a slug has many sessions (e.g. Mamma Mia with 76 sessions).

## Category mapping

Genre names come from `show.genre.name.ca`:

| genre_id | Genre (ca) | Category slug |
|---|---|---|
| 5 | Comèdia | `theater` |
| 6 | Dansa | `dance` |
| 7 | Monòlegs | `theater` |
| 9 | Musical | `theater` |
| 10 | Ponència | `theater` |
| 11 | Infantil | `kids` |
| unknown | — | `theater` (default) |

## Price

**Systematically unavailable.** Price is not published on the balanaenviu.com
website (not in the API JSON, not in the listing HTML, not on event detail pages).
All events have `price=None` except sold-out events which carry `price="sold-out"`.

The sold-out / cancelled status is inferred from the `.customLabel` element inside
each `.box` in the listing HTML:
- "CANCEL·LAT" or "CANCELLED" → show is dropped entirely
- "SOLD OUT" → price set to `"sold-out"` for all occurrences

## Paral·lel 62

As of 2026-06-09, Paral·lel 62 (formerly BARTS) is **not listed** on
balanaenviu.com. The balanaenviu.com site covers only Tívoli, Coliseum, and
Borràs (theater IDs 2, 3, 4). IDs 1, 5–9 return zero shows. The venue's
former website (barts.cat) redirects to a summer festival, not a regular
programme. `Paralel62Scraper.scrape()` returns `[]` pending identification
of an authoritative events source.

## Quirks

- CSRF must come from the same session as the API call (cookie-bound).
- Month abbreviations in the ticketsBox use Catalan (JUN, JUL, SET, NOV…)
  with occasional Spanish fallback (ENE, SEP).
- The year for session dates is inferred: if the month is earlier than the
  current month, we assume next calendar year.
- The `.box__footer` date text (e.g. `12/06`) in the listing uses only DD/MM
  with no year — not used in parsing (we rely on the API's ISO datetime).

## Last verified: 2026-06-09

Cross-checked live output against browser for all three venues:
- Tívoli: 9 non-cancelled shows, Antonio Carmona (CANCEL·LAT) excluded, Una Noche Sin Luna sold-out ✓
- Coliseum: 12 shows, Que No Surti d'Aquí sold-out ✓
- Borràs: 12 shows, no cancelled/sold-out ✓
- Multi-session expansion verified: Mamma Mia → 76 sessions ✓
