# Harlem Jazz Club — scraper source map

Last verified against live site: 2026-06-01.

**Venue:** Harlem Jazz Club (Carrer de la Comtessa de Sobradiel, 8, Barcelona).
The oldest live-music room in Barcelona — jazz / blues / swing / world music.
WordPress + **EventON 4.8.2**.
**Categories produced:** `jazz` only (single-category venue; no club/DJ programming).

## Source

- **List URL:** `https://www.harlemjazzclub.es/conciertos/` — this page
  server-renders the WHOLE upcoming agenda (~42 EventON `.eventon_list_event`
  cards across several months) and is fully visible to a plain
  `httpx.get(..., follow_redirects=True)`. This is the primary (and only) source.
- **Do NOT use the homepage (`/`):** it only server-renders the next ~6 events and
  client-renders the rest, so `httpx` sees a partial list. `/conciertos/` has the
  full set.
- **There is no usable AJAX/REST endpoint.** EventON's `wp-json/eventon/v1/data`
  returns a `{"html":"test"}` stub for every endpoint name; the calendar's
  `admin-ajax` handler isn't publicly reachable. The server-rendered `/conciertos/`
  page makes all that unnecessary.
- **Do NOT trust the page-level / per-card JSON-LD blindly.** Each card embeds its
  own `<script type="application/ld+json">` Event, but the `description` contains
  raw unescaped HTML/newlines so the blob frequently fails `json.loads`. We only
  fall back to a *regex* extraction of its `"name"` field for the rare card that
  lacks a rendered `.evcal_event_title`.

## Per-field mapping (within each `.eventon_list_event` card)

| Field | Source |
| --- | --- |
| title | `.evcal_event_title` text, else regex `"name":"…"` from the card's JSON-LD; then strip the `HH:MMh \|` prefix, the trailing `(genres)` group and the trailing price |
| source_url | `[itemprop="url"]` href (query + trailing slash stripped) |
| external_id | card `data-event_id` (e.g. `8083`) |
| start_date | card `data-time` (first unix ts), converted in Europe/Barcelona (UTC+2); fallback = `meta[itemprop=startDate]` date part |
| start_time | the `HH:MMh` **title prefix** (the real showtime) — NOT `data-time`/`startDate`, which encode the earlier bar-opening time. No prefix ⇒ None |
| price | trailing `NN€` of the title (free text, e.g. `15€`); `Entrada libre`/`Gratis`/`lliure` ⇒ `"Entrada libre"`; none ⇒ None |
| annotations | the genres in the LAST `(...)` group of the title, split on commas (e.g. `["blues","early jazz"]`) |
| image_url | `meta[itemprop="image"]` content |
| category_slugs | always `["jazz"]` (see discriminator) |

**Why the title and not the microdata for price/time:** the `.event-price`
microdata is wrong (reads `10`/`14` where the title says `11€`/`15€`), and the
`data-time`/`startDate` time is the bar-opening time (`20:30`) not the concert time
(`22:30h`). The human-facing title string is authoritative for title, showtime,
price and genres. Title format is consistent: `HH:MMh | NAME (genre, genre…) PRICE`.

## Category discriminator

**Always `jazz`.** This venue is a single-genre concert hall: there are no event
tags, no `event_type` taxonomy links, and no `+18`/DJ/disco listings on the page
(verified: 0 occurrences of `+18`, `disco`, or a standalone `DJ` in the agenda).
The granular musical styles in the title parens (swing, blues, flamenco, gipsy
jazz, soul, R&B, música cubana, bolero, jazz manouche, etc.) are **annotations**,
far too fine-grained to be top-level categories. If the venue ever adds a tagged
club/DJ night, revisit this rule — but as of 2026-06-01 none exist.

## Quirks

- **Duplicate cards:** EventON renders some events twice (a "this month" + a
  repeat block). Dedup by normalized `source_url` (81 url slots → 42 unique).
- **Lightbox template card:** one trailing `.eventon_list_event.evo_lightbox_body`
  popup template has no url/data-time — skipped explicitly.
- **`CERRADO POR LA NOCHE DE SAN JUAN`** (venue-closed notice for San Juan night)
  has no `HH:MMh` prefix, no genres and no price → title kept verbatim, time/price
  None, annotations `[]`. It is a legitimate listing, so it is emitted.
- `startDate` meta is non-zero-padded ISO (`2026-6-2T20:30+2:00`) — handled only by
  the regex fallback; the primary date path uses the unix `data-time`.
- Result over the live fixture (41 events): price 98%, showtime 98%, annotations
  98%, category 100%, image 100%, external_id 100%. The ~2% gaps are the single
  San Juan closed notice.

## Verification (Phase 4, 2026-06-01)

Ran `parse_agenda(fixture)` and live `scrape()` — both yield 41 events with the
coverage above and `categories == {"jazz"}`. Cross-checked the first 6 events
field-by-field against the live browser DOM (`.evcal_event_title` + `startDate`
meta): titles, dates, showtimes (from the title prefix), prices and genre
annotations all agree exactly.

## Seed requirements

> The parent agent must integrate the following into `seed.py` / `test_seed.py`
> (this scraper intentionally does not touch them).

- **venue slug:** `harlem-jazz-club`
- **display name:** `Harlem Jazz Club`
- **address:** `Carrer de la Comtessa de Sobradiel, 8, 08002 Barcelona`
- **site_url:** `https://www.harlemjazzclub.es`
- **category slugs produced:** `{ jazz }` (single category)
- **list membership:** add to the **jazz** cartelera category list. As a
  single-category venue it should be added with a **NULL `whitelist_category_id`**
  (all its events belong to the jazz list). It does NOT belong to the club list.
