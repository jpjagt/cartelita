# Zumzeig Cinecooperativa — source map

Venue slug: `zumzeig`. Single-category venue: **film** (an independent cooperative
arthouse cinema in Sants, Barcelona; every session is a film screening — the
`tipo` attribute is a *programming cycle* (paralleles/estrenes/infantil/
festivals/experimental), not a top-level category).

Own site: `https://zumzeigcine.coop`. (A directory link to mabuse.es exists but is
a third-party aggregator and is NOT used.)

## List URL

- Calendar: `https://zumzeigcine.coop/cinema/calendari/`
  - Server-renders a month-grid `<table>` per upcoming month (currently June + July
    in one page load — **no pagination/params needed**; the page shows all
    currently-programmed sessions, ~6 weeks out).
  - The `/cinema/sessions/` ("Cartellera") list view also exists but groups by
    *film* and truncates a film's sessions with a `+` marker (`strong.plussesion`),
    so it does NOT list every occurrence. The **calendar is authoritative** — one
    `<a class="sessio">` per occurrence, with the date on its parent cell.

## Data source (server-rendered HTML — no JS needed)

The calendar is plain server HTML (the `rel` ISO date attributes are present in the
raw response; confirmed via `httpx`/curl, not just the rendered DOM). Structure:
`<td class="day" rel="YYYY-MM-DD">` cells, each containing zero or more
`<a class="sessio" tipo="..." filmid="..." href="...">` — **one `<a>` = one
screening occurrence**. Per `a.sessio`:

| Field            | Source                                                                 |
|------------------|------------------------------------------------------------------------|
| `start_date`     | parent `td.day[rel]` → `rel="YYYY-MM-DD"` (ISO, no parsing of the Catalan `Dt 2.6.26` text needed) |
| `start_time`     | `.hora` text (`"18:30"`); a trailing `*` is stripped (see below)        |
| `title`          | `.film` text                                                           |
| `source_url`     | `href` → `/cinema/films/<slug>/` (abs-ified to `https://zumzeigcine.coop`) |
| `external_id`    | `<filmid>@<date>T<HHMM>` — film id qualified by the occurrence (below)  |
| `image_url`      | not on the calendar; taken from the `/cinema/sessions/` card thumb is possible but skipped (one request beats N) → None |
| `annotations`    | the cycle (`tipo`, title-cased) + `"acompanyat"` when the screening has a guest/colloquium (the `*` / `span.acompanyat`) |
| `category_slugs` | always `["film"]`                                                       |
| `price`          | **None** — see below                                                    |

### Date / time rule

`td.day[rel]` carries the screening's local date as an ISO string — used directly.
`.hora` is the local wall-clock time `HH:MM`. A trailing `*` (rendered separately
as `span.acompanyat` in the Cartellera view) marks an **accompanied** screening
(guest/colloquium/presentation); we strip it from the time and record
`"acompanyat"` as a free-form annotation.

### category / cycle

Every session is category `film`. The `tipo` attribute
(paralleles/estrenes/infantil/festivals/experimental) is a programming **cycle**,
too granular for a top-level category, so it goes into `annotations`
(title-cased), not `category_slugs`.

### `external_id`

The film id (`filmid` attr) is **coarser than an occurrence** — the same film
screens on several dates (e.g. "Corredora" runs 2 Jun, 3 Jun, 10 Jun). The upsert
dedups on `(venue, external_id)` and one Event row is one occurrence, so a bare
film id would collapse occurrences (the Filmoteca trap). We qualify it with the
occurrence's date+time: `<filmid>@YYYY-MM-DDTHHMM`. The `source_url` stays the bare
film page (shared across screenings, by design).

### price

The site does **not** expose a scrape-able ticket price. The calendar and film
detail pages carry no price; the cooperative's Informació/Participa pages describe
the membership model in prose, not a flat single-ticket rate, and the "Entrades"
buttons hand off to a JS ticketing flow. Per the price convention, an
un-scrape-able price is `None` (not a guessed value). The free-entry phrases to
normalize **if** they ever appear on the calendar/detail (Catalan): "Entrada
gratuïta", "Activitat gratuïta", "entrada lliure" → `"free"`; none are present
today.

## i18n

The calendar is available in Catalan (`/cinema/calendari/`) and Spanish
(`/es/cine/calendari/`). Titles on the calendar are already in the film's own
language (Catalan or Spanish, e.g. "¿Qué te dice esa naturaleza?"). We scrape only
the Catalan calendar — the list page is a complete event on its own — and emit no
translations.

## Quirks

- `/cinema/sessions/` truncates a film's session list with a `+`
  (`strong.plussesion`) marker → do NOT use it for occurrences; the calendar has
  the full set.
- The raw calendar HTML repeats `class="sessio"` twice on each `<a>` and renders
  one `<table>` per month (June + July); BeautifulSoup parses this cleanly to 49
  `a.sessio` (`td.day[rel]` count is higher because empty day cells also carry
  `rel`).
- `zumzeigcine.coop` serves its own content directly (HTTP 200, title "Zumzeig").
  A stale browser session may show a cached redirect to espaitexas.cat — that is a
  *different* venue, not Zumzeig; `httpx`/curl never redirect there.

## Verification (2026-06-01)

Live scrape: **49 events**, 2026-06-01 → 2026-07-12. Coverage: start_time 49/49,
category 49/49 (`film`), external_id 49/49 (all unique), annotations 49/49; price
0/49 (None, by design — no scrape-able price); image_url 0/49 (not on the
calendar). Field-by-field cross-check of the first 8 sessions against the live DOM
(date / time / title / cycle / accompanied `*`) — all agree. Confirmed the
per-occurrence external_id: "Corredora" (filmid 14063) screens 4× (2 Jun 12:00,
3 Jun 17:00, 10 Jun 18:00, 12 Jun 17:15) and survives as 4 distinct events.

last verified: 2026-06-01
