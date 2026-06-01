# 23 Robadors — scraper source map

Last verified against live site: 2026-06-01.

**Venue:** 23 Robadors / Harlem Jazz Club (Carrer d'en Robador, 23, El Raval, Barcelona).
WordPress + "The Events Calendar" plugin (tribe-no-js body class).
**Categories produced:** `jazz` (all events — flamenco, jazz sessions, and jam nights all map to jazz).

## Source

- **List URL:** `https://23robadors.com/` (homepage) — the only page that renders
  the full agenda (~55 events) in a single request. The routes `/agenda/`,
  `/events/`, and `/programacio/` all 301-redirect back to the homepage.
  `/calendari/` exists but only shows ~30 events; the homepage is preferred.
- **Data source: JSON-LD only.** A single `application/ld+json` script tag on
  the homepage carries a JSON array of `Event` objects. This is the primary
  and only source — unlike Jamboree, the JSON-LD here is **complete**: it
  carries name, startDate, endDate, image, url, `offers.price`, and
  `offers.priceCurrency`. No DOM card parsing is needed.
- **Do NOT use the DOM calendar.** The homepage embeds a monthly calendar widget
  with event data in `<i title="...">` attributes, but this is harder to parse
  than the JSON-LD and covers the same data.

## Per-field mapping (from each JSON-LD Event object)

| Field | Source |
| --- | --- |
| title | `name` (HTML-entity-decoded, stripped) |
| source_url | `url` (trailing slash + query stripped) |
| external_id | the `/calendari/<slug>` segment from `url` |
| start_date / start_time | `startDate` ISO 8601 timestamp (TZ offset stripped; wall-clock kept) |
| end_date / end_time | `endDate` (same); dropped if equal to startDate+startTime |
| price | `offers.price` + `offers.priceCurrency` → `"10€"`, `"5€"`, `"free"` (price=0); `None` if absent |
| image_url | `image` |
| annotations | genre string from `description` (see Category discriminator below) |
| recurrence_hint | `"weekly"` when title contains "jam" |

## Category discriminator

23 Robadors is a pure live-music venue (jazz and flamenco). All events map to
the `jazz` top-level category. The `description` field encodes a one-line genre
keyword:

| Description value | category_slugs | annotations |
| --- | --- | --- |
| `FLAMENCO` | `["jazz"]` | `["flamenco"]` |
| `JAZZSESSION` | `["jazz"]` | `["JAZZSESSION"]` |
| `LA JAM DE JAZZ` | `["jazz"]` | `["LA JAM DE JAZZ"]` |
| `JAZZSESSION / COL·LECTIU VINT·I·TRES` | `["jazz"]` | `["JAZZSESSION", "COL·LECTIU VINT·I·TRES"]` |
| `JAZZ / CONCERT + JAM / COL·LECTIU VINT·I·TRES` | `["jazz"]` | `["CONCERT + JAM", "COL·LECTIU VINT·I·TRES"]` |
| (other) | `["jazz"]` | verbatim parts from description |

Flamenco events use category `jazz` (best-fit, as instructed) and get the
`flamenco` annotation for downstream filtering. No title-keyword logic is used
for categorisation — the `description` field is the authoritative genre signal.

Closure notices (`TANCAT / CLOSED`) are skipped entirely.

## Quirks

- **Double-encoded HTML entities in description:** The JSON-LD `description` is
  stored as HTML-entity-escaped markup (e.g. `"&lt;p&gt;FLAMENCO&lt;/p&gt;\\n"`).
  The scraper calls `html.unescape` then BeautifulSoup to extract the text, and
  also strips literal `\n` sequences left by the WordPress Events plugin.
- **Price coverage ~87%:** 8 of ~55 events lack a price. These are free
  community sessions (COL·LECTIU VINT·I·TRES), talent festival shows (TALLER
  DE MÙSICS), or one-off special events. Price `"0"` is mapped to `"free"`.
- **endDate quirk:** Many events have `endDate == startDate` exactly (same
  timestamp). These are dropped to avoid confusing `end_time == start_time`.
- **Times are local Barcelona wall-clock** (TZ offset in startDate stripped);
  we keep them naive, same as the Jamboree scraper.

## Seed requirements

**Venue slug:** `robadors`
**Display name:** `23 Robadors`
**Address:** Carrer d'en Robador, 23, El Raval, 08001 Barcelona
**site_url:** `https://23robadors.com`
**Category slugs produced:** `jazz`
**List membership:** should appear on the `jazz` cartelera list (no whitelist
category needed — the venue produces only `jazz` events, so `whitelist_category_id`
can be NULL).
