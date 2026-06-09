# Antic Teatre — scraper source map

Last verified against live site: 2026-06-09.

**Venue:** Antic Teatre — Espai de Creació (Sant Pere, Barcelona). An independent
experimental / multidisciplinary performing-arts space in a 1650 building.
WordPress + Yoast SEO.
**Categories produced:** `theater` (drama, performance, circus, community arts),
`dance` ("nous llenguatges del cos" / "dansa" category label).

## Site structure

The programme is organized by month. Current months (3) are linked from the
`PROGRAMACIÓ` nav sub-menu on:

  `https://www.anticteatre.com/programacio/`

The sub-menu links use opaque WordPress slugs like `programacio/4-mesos-vista-2-2/`
(June), `…-2-2-2/` (July), `…-2-2-2-2-3/` (September). These change when the
season rolls over — the scraper discovers them dynamically from the nav each run.

## Data sources (two-layer strategy)

### Layer 1 — Monthly list pages (one per month)

Each page is a flat list of `.row` cards. One row per occurrence (a show running
Th–Sun appears as 4 rows). No pagination. Fields per row:

| Field | Selector |
|---|---|
| day-of-month | `.entry-day-num` text |
| month + year | `h2.archive-title` text (e.g. "Juny 2026") |
| start_time | `.entry-time` text if matches `HH:MM`; else None (e.g. "L'Antic al GREC 2026.") |
| title | `.entry-title` text |
| author/company | `.entry-author` text (→ first annotation) |
| category label | `.entry-category.no-mobile` text (usually populated; sometimes empty for cycle events) |
| extra badge | `.entry-extra` text ("estrena Barcelona", "Cicle mensual", etc.) |
| detail URL | `.entry-link` href |

**Note on line-break hyphens:** Circle span elements use mid-word line-breaks
represented as either a soft-hyphen U+00AD (e.g. `lleng\xad uatjes`) or a plain
ASCII hyphen-minus followed by a space (`lleng- uatjes`). The `_clean()` helper
strips both so category lookup works correctly.

### Layer 2 — Event detail pages (one per unique show URL)

12 unique shows → 12 detail page fetches per scrape. Fields from detail:

| Field | Selector |
|---|---|
| category (full) | `.entry-category .circle span` (not `.entry-extra`) |
| price raw | `.entry-price` text (stripped of "Entrades:" label prefix) |
| image_url | first `img[src*="wp-content/uploads"]` on the page |

**Price formats seen:**
- `"15 euros ONLINE // 17 euros TAQUILLA"` → two tiers, 15 and 17 → high < 2× low → `"17€"`
- `"8,5 euros ONLINE i 10 euros TAQUILLA"` → 8.5 and 10 → `"10€"` (comma decimal)
- `"Entrada gratuïta"` → `"free"`

Detail pages have occasional SSL EOF errors on connection; the scraper catches
exceptions per URL and emits the event from list data anyway (price stays None).
Coverage was 100% on the verified run but may dip to ~90% on intermittent errors.
The scraper uses `verify=False` + a `User-Agent` header to work around the TLS issue.

## Category discriminator

All Antic Teatre programming maps to two categories:
- `dance` — when the category circle label (after cleaning) is `"nous llenguatges del cos"`, `"dansa"`, or `"dance"`.
- `theater` — everything else (performance, noves dramatúrgies, teatre, circ, arts escèniques comunitàries, etc.).

Category is read from the detail page (`.entry-category .circle span`); the list
page category (`.entry-category.no-mobile`) is used as a fallback when the detail
fetch fails.

## external_id

Per-occurrence: `{show-slug}@{YYYY-MM-DD}T{HHMM}` where the show-slug is the last
path segment of the event URL (e.g. `peti-suis-cia-supreema@2026-06-04T2000`).
For GREC events with no parsed time, HHMM = `0000`. This ensures each occurrence
of a multi-night run gets a distinct dedup key.

## Annotations

Each event's annotations list (in order):
1. Author/company (`entry-author`)
2. Site category label from the list page (the free-text display label, not the slug)
3. Extra badge if present ("estrena Barcelona", "Cicle mensual", etc.)
4. Venue/festival note for off-site events (e.g. "L'Antic al GREC 2026.")

## Seed requirements

- **venue slug:** `antic-teatre`
- **display name:** `Antic Teatre`
- **address:** `C/ de Verdaguer i Callís, 12, 08003 Barcelona`
- **site_url:** `https://www.anticteatre.com`
- **category slugs:** `theater`, `dance`
- **list memberships:** `theater` list (whitelist `theater`), `dance` list (whitelist `dance`)

## Verification (2026-06-09)

Live `scrape()`: **48 events** across June, July, September 2026.
- Price coverage: **48/48 (100%)** — all events had detail pages reachable
- Categories: `theater: 36`, `dance: 12`
- start_time coverage: 32/48 (67%) — 16 GREC events have no clock time (annotated)
- Image coverage: 40/48 (83%) — detail page fetches that succeed include image
- Field-by-field browser cross-check of June programme: title, time, author, and
  title for all 14 rows matched the live page exactly. Peti-suis (4 occurrences
  Thu–Sun, "17€", category "theater") confirmed against detail page.

## Quirks

- Monthly list page URLs are opaque WordPress slugs that will change when the
  season rolls over. The scraper discovers them dynamically from the nav — no
  hardcoded month URLs.
- GREC off-site events ("L'Antic al GREC 2026.") appear in the July page with no
  time (the time slot holds the festival label). These are real events that belong
  in the calendar; start_time is None and the note is in annotations.
- The detail page for "QUAN SIGUI GRAN" has two circles: `Teatre` + `estrena`
  (the `estrena` is in `.entry-extra`, not `.entry-category` — correctly filtered out).
- Soft-hyphen/line-break hyphens in circle spans: handled by `_clean()`.
