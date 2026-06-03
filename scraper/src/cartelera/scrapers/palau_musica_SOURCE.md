# Palau de la Música Catalana — source map

last verified: 2026-06-02

## Venue
- slug: `palau-musica`
- name: Palau de la Música Catalana
- city: barcelona
- address: C/ Palau de la Música, 4-6, 08003 Barcelona
- site: https://www.palaumusica.cat

## List URL / data source
The public programme page is `https://www.palaumusica.cat/ca/programacio_1158636`
(the `/en/programme` and `/ca/programa` paths the task mentioned return 404 — the
real path is the woost id-suffixed `programacio_1158636`). That page renders the
concert listing **client-side** via `sessionlisting.js`; the static HTML carries
no events. The script fetches a single clean JSON document from:

```
https://www.palaumusica.cat/ca/programming_data_json?palau_productions=1&orfeo_productions=0&espaisoci_productions=0&sessions_as_dict=1
```

This JSON is the scraper's sole, robust data source (no per-event detail fetches
needed). `parse_programming(json_text)` is the pure parse function.

### JSON shape
Top-level dict with keys `productions`, `sessions`, `hashtags`, `cycles`,
`stages`, `tags`, `organizers` — each a `{id_str: record}` map.

- **production** record: `id`, `title`, `subtitle`, `url`, `price` (free-text),
  `gratis` (bool), `hashtags` (list of hashtag ids), `cycles` (list of cycle ids),
  `listing_image` (image id), `listing_image_ext`, `season`, `hidden`, `external`
  (true = external organizer renting the hall — still part of the programme, kept).
- **session** record (one per OCCURRENCE): `production` (id), `start_date`
  (`{value: "YYYY-MM-DD HH:MM", label, ts}`), `stage` (id), `expired` (bool),
  `hidden` (bool), `uncertain_start_time` (bool).
- **hashtag**/**cycle**/**stage** records carry a `title`.

## Per-field mapping
- **title** ← production.title (HTML stripped; the field wraps text in `<p>`).
- **subtitle** → first annotation (HTML stripped).
- **start_date / start_time** ← session.start_date.value (`YYYY-MM-DD HH:MM`,
  Barcelona wall-clock, kept naive). If `uncertain_start_time` is true, time → None.
- **source_url** ← production.url.
- **price** ← production.price normalized to the project convention (free text):
  - `gratis` true, or price text matching gratuït / accés lliure / lliure → `"free"`.
  - "concert per invitació" / no numeric value → `None`.
  - "de X a Y €" / "X i Y €" / "De X a Y euros" → `"X–Y€"` (range).
  - "X €" / "X" / "X.0" → `"X€"`.
  - Member/discount tiers after `(`, `/`, "socis", "abonats", "Palau Jove",
    "especial", "discapacitat" are dropped; we keep the main public price/range.
- **image_url** ← `/images/{listing_image}/production_listing{listing_image_ext}`.
- **annotations** ← subtitle + cycle titles + hashtag titles (with `#` stripped)
  + non-Palau stage title when off-site. The hashtags/cycles are genre/series
  labels, too granular for a top-level category — kept here, never in category_slugs.
- **external_id** ← `"{production_id}@{date}T{HHMM}"` — per-OCCURRENCE. A production
  may have many sessions (and `start_date` repeats across stages on the same day),
  so the id is qualified with date+time to avoid collapsing occurrences in the upsert.

## Filtering
Emit a session only when `session.expired` is false, `session.hidden` is false,
and its production exists and is not hidden. The venue's own `expired` flag is the
source of truth for "past" (do not re-filter by today's date).

## Category rule
Default `classical`. The truthful per-event override is driven by the production's
**hashtags**:
- `#jazz` → `jazz` (the "58 Festival de Jazz de Barcelona" cycle, etc.).
- everything else → `classical`.

### New-category candidates (NOT invented — flagged, fall back to classical)
The programme also contains genres we have no top-level category for. These are
emitted as `classical` for now and surfaced in `annotations`:
- `#flamenc` (flamenco galas / "De Cajón!" festival) — would warrant a `flamenco`
  category.
- `#cinema` (film-with-live-orchestra) — closest existing is `film`, but these are
  concert-format screenings; left as `classical`.
- `#conferències` / talks — would warrant a `talk`/`conference` category.

## Quirks
- The site is a woost/cocktail CMS; programme is JS-rendered, so we hit the JSON
  endpoint directly rather than parsing rendered HTML.
- The JSON holds ALL seasons (1217 productions, 2048 sessions); the `expired`
  flag narrows it to the ~390 upcoming occurrences shown on the live page.
- No price appears in the rendered DOM cards; price lives only in this JSON
  (and on ticketing pages). Price coverage from the JSON is ~99%.
- `start_date.value` has minute precision; a couple of records may have an empty
  value — those are skipped.

## Verification (2026-06-02)
`uv run python` standalone run of `PalauMusicaScraper().scrape()` produced ~392
events, ~99% with a price, all with valid dates/titles/urls, categories
{classical, jazz}. Cross-checked the first several productions (titles, dates,
cycles, prices) against the rendered programme page in the browser — they agree.
