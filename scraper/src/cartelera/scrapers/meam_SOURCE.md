# MEAM (Museu Europeu d'Art Modern) — source map

Venue slug: `meam`. **Multi-category** venue: a classical concert series and music
(blues / folk) series share the same programme. An art museum in Barcelona's Born
district whose Gomis Palace hosts weekly concert series.

Own site: `https://www.meam.es`.

## List URL

- Diary listing: `https://www.meam.es/en/diary/`
  - Server-renders one `<li class="grid-item">` per upcoming concert occurrence
    inside `<ul class="events-grid">`. **Authoritative** — every occurrence in one
    page load, no pagination/params needed (~18 upcoming concerts, ~10 weeks out).
  - The `/en/activities` page shows the same events but only a small carousel
    (`div.grid-item`, ~8 items) — NOT every occurrence, so we use `/en/diary/`.
  - We scrape the **English** locale (`/en/diary/`) so series labels are stable
    English strings; `ca`/`es`/`fr`/`it` mirrors exist at the analogous paths.

## Data source (server-rendered HTML — no JS needed)

Confirmed present in the raw `httpx` response (not just the rendered DOM). Per
`li.grid-item`:

| Field            | Source                                                                          |
|------------------|---------------------------------------------------------------------------------|
| `title`          | `h3.short a` text, with the ` | <series>` suffix stripped off                    |
| `source_url`     | `h3.short a` `href` → `/en/diary/<id>/<slug>.html` (already absolute)            |
| `start_date`     | `.meta-data` line `"Fri,  5 Jun 2026 18:00"` → day + abbr-month + year           |
| `start_time`     | same `.meta-data` line → `"18:00"`                                               |
| `image_url`      | card `img[src]` (a `php/rz.php` resizer URL)                                     |
| `annotations`    | the series label (e.g. `"Friday Blues"`, `"Saturday Classics"`, `"Sunday Sounds"`) |
| `category_slugs` | derived from the series (below)                                                 |
| `price`          | NOT on the listing → enriched from the detail page (below)                       |
| `external_id`    | `<diary-id>@<date>T<HHMM>` (below)                                               |

### Category mapping (the discriminator)

The venue groups concerts into named **series**, rendered as the ` | <series>`
suffix of every card title (and mirrored in the URL slug, e.g.
`...-saturday-classics.html`). We split the title on the last ` | ` and map the
series → our top-level category:

| Series                        | Category    | Note |
|-------------------------------|-------------|------|
| `Saturday Classics`           | `classical` | chamber/classical recitals |
| `Friday Blues` / `Friday's Blues` | `jazz`  | **closest existing** — see recommendation below |
| `Sunday Sounds`               | `jazz`      | intimate folk / contemporary acoustic — not classical |

Any future/unknown concert series defaults to `jazz` (the music bucket). The series
label itself is kept as a free-form `annotation`, never as a category.

**New-category recommendation:** "Friday Blues" is blues, which is closer to `jazz`
than to `classical` but is not really jazz. A dedicated **`blues`** category would
be the truthful label. Per the project rule we do NOT invent it silently in code;
we fall back to `jazz` and flag the recommendation here. (Likewise "Sunday Sounds"
is folk; if a `folk` category is ever added it should move there.)

### price

Not present on the diary listing. Each detail page carries a single
`<h3 class="short">` price line, e.g.
`"Advance ticket sales: 18.00€ / Price at the entrance: 18.00€"`. We fetch the
detail pages concurrently (best-effort) and `normalize_price`:
- multiple `€` amounts → the **highest** public amount, rendered concise (`"18€"`);
- free-entry phrases (`free admission`, `entrada gratuïta`, `entrada libre`, …) → `"free"`;
- sold-out phrases (`sold out`, `esgotat`, `agotad…`) → `"sold-out"`;
- nothing parseable → `None`.

### `external_id`

The diary id (e.g. `1415`) is unique per concert occurrence today (each diary entry
is one dated session). We still qualify it with the occurrence date+time
(`<id>@YYYY-MM-DDTHHMM`) so the key stays per-occurrence-safe if the venue ever
reuses an id across sessions (the upsert dedups on `(venue, external_id)` and raises
on an in-batch duplicate).

## i18n

The same events exist under `/ca/`, `/es/`, `/fr/`, `/it/` path prefixes. We scrape
only the English diary (the listing is a complete event on its own) and emit no
translations. Concert/performer titles are largely language-neutral anyway.

## Quirks

- Title separator is a literal ` | `; we split on the **last** `|` (titles like
  `Golden Lowlands - Intimate Folk for Voice and Strings | Sunday Sounds` contain a
  hyphen but no other pipe).
- Some titles contain stray control bytes from the CMS (`\x96` en-dash, `\x85`
  ellipsis); `_clean` maps `\x96` → `-` and unescapes entities.
- `/en/activities` is a small carousel (`div.grid-item`); `/en/diary/` is the full
  `li.grid-item` list — do not confuse the two selectors.

## Multi-list membership

This venue emits **two** categories (`classical` + `jazz`). The VenueDefinition
declares both in `category_slugs`. For list wiring it currently joins the
`classical` list (whitelisted to `classical`); a `jazz`-list membership (and/or a
future `blues` list) should be added by the parent when wiring the seed, so the
blues/folk events surface in the right music list.

## Verification (2026-06-02)

Live scrape (`MeamScraper().scrape()`): **18 events**, 2026-06-05 → 2026-08-14.
Category split **13 jazz** (Friday Blues ×11 + Sunday Sounds ×2) / **5 classical**
(Saturday Classics). Coverage: start_date 18/18, start_time 18/18 (all 18:00), category 18/18,
external_id 18/18 (all unique), annotations 18/18 (series), image_url 18/18, price
18/18 (`18€`, from the detail pages). Field-by-field cross-check of the first cards
against the live diary DOM (date / time / title / series) — all agree.

last verified: 2026-06-02
