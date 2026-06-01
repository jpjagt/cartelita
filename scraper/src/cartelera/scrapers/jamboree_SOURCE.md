# Jamboree — scraper source map

Last verified against live site: 2026-06-01.

**Venue:** Jamboree (Plaça Reial, 17, Barcelona). WordPress + "The Events Calendar".
**Categories produced:** `jazz` (concerts) and `club` (+18 DJ nights).

## Source

- **List URL:** `https://jamboreejazz.com/agenda/llista/` — the `llista` (list)
  view renders rich `<article>` cards for the WHOLE agenda (both Concerts and
  Disco sections in one page), each with title, price, genre tags, and a detail
  link. This single page is the primary source.
- **Do NOT rely on JSON-LD alone:** the page's `application/ld+json` Event blob
  has clean `startDate`/`endDate`/`name`/`image`/`location` but **omits price and
  category**. We use it only to recover clean ISO datetimes, keyed by detail URL.
- The separate `/disco/` page lists only club events and has a different
  structure (no article cards); we don't need it — the list view already
  includes the club events.

## Per-field mapping (within each `<article>`)

| Field | Source |
| --- | --- |
| title | first non-empty `a[href*="esdeveniment"]` text |
| source_url | that link's href (normalized, trailing slash + query stripped) |
| external_id | the `/esdeveniment/<slug>` segment |
| price | `.preu-normal` text (e.g. `12€`); `"s.o."` if "Sold out" present, else None |
| start/end date+time | from JSON-LD Event matched by normalized url; all-day sentinel `00:00–23:59:59` → time None |
| category | tag-driven: `a[href*="/tag/"]` texts; if they include `+18` → `club`, else `jazz` |
| annotations | the genre tags minus `+18` (e.g. `Jazz`, `Bossa Nova`, `Soul`, `Trap`) |
| recurrence_hint | `"every Monday"` when title contains "jam session" |

## Category discriminator

The `+18` tag (`/tag/18/`) marks club/disco nights (recurring resident "… Night:
DJ …" sets). Everything else is a jazz concert. **Title keywords are NOT
reliable** — some jazz concerts ("Tk Mami (+DJ Aft3rlife)", tagged `Trap`)
mention a DJ but are not club nights. Use the tag, not the title.

## Quirks

- ~247 events in the list at a time. Price coverage ~100%; annotations on ~85%.
- The genre tag vocabulary is large (~88 distinct sub-genres) — these are
  annotations, far too granular to be top-level categories.
- Times are local Barcelona wall-clock in the JSON-LD; we keep them naive.
