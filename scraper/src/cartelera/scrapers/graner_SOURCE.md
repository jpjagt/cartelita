# Graner — source map

Graner (https://granerbcn.cat/) is a **dance / live-arts creation centre** in
La Marina (Port), Barcelona. Public dated activities are sparse (a handful per
month — presentations, workshops, neighbourhood activations). All programming is
`dance`.

## Data source

WordPress (Webflow-exported templates), WPML multilingual (ca / es / en).

The events agenda is rendered **server-side in the homepage HTML** in
`.home-agenda__container` — one current-month "schedule" block.

- Catalan (canonical):  `https://granerbcn.cat/`
- English (translation): `https://granerbcn.cat/en/`

The standalone agenda/archive template is a known **gotcha**: it renders only a
single PLACEHOLDER card ("titol", date "2/2/2023") and does not load the real
events. Do NOT use it. The WP REST API (`/wp-json/wp/v2/types`) exposes only
`post`/`page` — the custom post types (`programes`, `arxiu`, `activitat`, ...) are
NOT REST-enabled, and detail pages carry no structured date/time/price (they are
free-text residency descriptions). The homepage agenda block is the only clean,
structured, dated source.

### Per-field source (within each `.home-agenda__element`)

| Field        | Source |
|--------------|--------|
| day          | `.home-agenda__date-day` text (e.g. "10") |
| month        | `.home-agenda__date-month` text — 3-letter uppercase abbrev, same across ca/es/en (e.g. "JUN", "JUL") |
| title        | `h5` text |
| source_url   | `a.home-agenda__link[href]` (may be external, e.g. beteve.cat) |
| image_url    | `img[src]` |
| start_time   | not structured anywhere -> None |
| price        | not on the site; left unknown (None) |

Year is inferred: current year, rolled forward to next year if the parsed month
is earlier than the current month (handles a Dec->Jan boundary).

## Category mapping

Single venue category: **`dance`** (Graner is a dance/live-arts creation centre).
No per-event discriminator exists; everything is `dance`.

## external_id

`graner-<YYYY-MM-DD>-<url-slug>` — per occurrence (date + slug).

## Translations

Catalan homepage is canonical; English title/url added as a `ca`->`en`
`ScrapedTranslation` keyed by matching the `(day, month)` slot across the two
homepages.

## Quirks

- Placeholder-template gotcha (above).
- Agenda shows only the current month; programming is intentionally sparse — a
  low event count (often < 5) is EXPECTED, not a scrape failure.
- Some events link off-site (beteve.cat); URL kept as-is.

Verified: 2026-06-09
