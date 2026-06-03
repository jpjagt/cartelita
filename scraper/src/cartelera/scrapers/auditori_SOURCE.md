# L'Auditori — source map

**Venue:** L'Auditori de Barcelona (home of the OBC — Barcelona Symphony
Orchestra — and the Banda Municipal de Barcelona / BMB). Classical-first.

**Last verified: 2026-06-02**

## List URL / data source

The public listing at `https://www.auditori.cat/ca/esdeveniment/` is a
JS-rendered WordPress shell — the raw HTML contains an empty `.a-events-block`
container and **zero** event cards (cards are injected client-side). So we do
NOT scrape the HTML page.

The cards are populated from a WordPress admin-ajax endpoint that returns clean
JSON and is hittable directly with `httpx` (no browser needed):

```
https://www.auditori.cat/wp-admin/admin-ajax.php
    ?action=get_auditori_events_query
    &page=1
    &limit=500                 # one request returns the whole programme (~174 events)
    &output_profile=all        # 'all' includes per-session data + price + taxonomy;
                               # the default 'basic_card' profile omits sessions
    &from_date=false
    &hide_in_page=true
```

Response is a JSON **list of event objects**. `parse_agenda(text)` does
`json.loads(text)` and walks the list. The saved fixture
(`tests/fixtures/auditori_agenda.html`) is this JSON response with the heavy
unused fields (`post_content`, `video`, `carousel`, etc.) trimmed off; every
field the parser reads is preserved verbatim.

## One row per SESSION (occurrence)

Each event object has a `sessions` list; each session is one real occurrence
with its own `start_datetime`, `end_datetime`, `price`, `sold_out`, and `ID`.
We emit **one ScrapedEvent per session** (an event with 22 sessions → 22 rows).
Events with no sessions are skipped. 174 events → 248 sessions/occurrences.

### Per-field source (all paths are on the event object unless noted)

| ScrapedEvent field | Source |
|---|---|
| `title` | `wp_post.post_title` (HTML-unescaped) |
| `start_date` / `start_time` | session `start_datetime` (Unix ts) → `Europe/Madrid` local datetime. Exhibitions (`tax_etype_str == "Exposicions"`) are date ranges with a spurious museum-opening time, so their `start_time` is left `None`. |
| `end_time` | session `end_datetime` (same-day only; else `None`) |
| `end_date` | exhibitions only: event `event_date_last` (Unix ts) → date, when after start |
| `source_url` | `https://www.auditori.cat/ca/esdeveniment/{wp_post.post_name}/` (the `link` field is always null, so we build it from `post_name`) |
| `price` | session `price` (falls back to event `price_text`), normalized — see below |
| `external_id` | session `ID` (per-occurrence; globally unique session post id) |
| `category_slugs` | from `tax_ecategory_str` — see category rule |
| `annotations` | the granular labels: `tax_ecategory_str`, `tax_etype_str`, `tax_cicles_str`, and `subtitle` (HTML-unescaped, deduped) |
| `image_url` | `image_src` |
| `description` | `short_description` (HTML-unescaped) if present |

## Category rule

Discriminator is **`tax_ecategory_str`** (the venue's own programme category):

- `"Jazz & pop"` (HTML: `Jazz &amp; pop`) → **`jazz`** (Sit Back / Sessions /
  Escenes cycles: jazz, modern, pop concerts).
- Everything else → **`classical`** (default): `Simfònica` (OBC/BMB),
  `Cambra`, `Antiga`, `Nova Música`, `Educatiu`, `Social`, and empty.
  A combined value like `"Jazz & pop / Nova Música"` counts as jazz (contains
  "Jazz").

`Nova Música` is new/contemporary art music — it maps to `classical`, not a new
category. **No new category is needed.** The fine-grained programme labels
(`Simfònica`, `Cambra`, `Sit Back`, `OBC`, `BMB`, …) go into `annotations`,
never `category_slugs`.

## Price normalization

`price` free-text from the venue, normalized to the project convention:

- `"A determinar"` / empty → `None` (price TBD/unknown).
- Catalan free phrases (`accés lliure`, `entrada gratuïta`, `activitat
  gratuïta`, `gratu[ïi]t`) → `"free"`.
- `sold_out` flag truthy or `s.o.`/`exhaurit`/`sold out` text → `"sold-out"`.
- `"De 12 € a 16 €"` → `"12–16€"` (range).
- `"A partir de 25 €"` / `"25 €"` / `"25€"` / `"75 € / escola"` → highest single
  value, e.g. `"25€"` / `"75€"`.
- `"Entrada del Museu"` (museum-admission, no number) → `None`.

## Quirks

- `event.link` is always `null`; build the URL from `wp_post.post_name`.
- Timestamps are Unix seconds in `Europe/Madrid` (verified: "19h" / winter
  "11h" map correctly via `zoneinfo`, DST-safe).
- The raw `/esdeveniment/page/N/` HTML always serves the same cached first 10
  events — do NOT paginate the HTML; use the ajax `limit` param instead.
- HTML entities (`&#039;`, `&amp;`) appear in titles/subtitles → `html.unescape`.
- As of verification no session was sold-out or canceled, but both flags are
  handled.

## Verified (2026-06-02)

Ran the live scraper and cross-checked the first events against the rendered
`/ca/esdeveniment/` cards in the browser: title, date·time, price, and category
agree field-by-field (e.g. "LA BANDA AL PALAU DE LA MÚSICA" → 11 Jun 2026 19:00,
25€, classical; "L'ocell de foc de Stravinsky…" → 12 & 13 Jun, classical).
248 occurrences, 100% price coverage, 100% category coverage.
