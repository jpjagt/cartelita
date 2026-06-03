# Casa Batlló — "Magical Nights" — source map

Venue slug: `casa-batllo`. Module: `casa_batllo`. Live rooftop concerts on Gaudí's
building (Passeig de Gràcia 43, Barcelona): a guided visit + a glass of cava + a
live concert on the terrace.

Own site: `https://www.casabatllo.es`.

## Category — IMPORTANT (does not match the brief's expectation)

The brief expected classical-crossover / strings. The actual **2026 lineup is
contemporary / world live music — NOT classical**: soul, funk, disco, jazz, swing,
blues, rumba, flamenco, bossa, boleros, salsa, pop, rock, R&B. The venue's own
banner reads "SOUL, JAZZ, FLAMENCO, RUMBA...". There is **no classical / strings
act** in the programme.

Existing categories are `film, jazz, classical, theater, club`. None fits this
general live-music programme cleanly. Per the category rule we map to the **nearest
existing music category, `jazz`** (many acts are genuinely jazz/swing/blues, and
the rest are still contemporary live music — `jazz` is closer than `classical`,
`theater`, `club` or `film`). The granular per-act genre string ("Funk, Soul,
Disco", "Rumba, Flamenco, Rock", …) is preserved verbatim in `annotations`.

**New-category recommendation:** a top-level `live-music` (or `concerts`) category
is the truthful fit for this venue (and would also better fit other pop/world live
acts elsewhere). Until that exists, this scraper emits `jazz` and the venue's
`list_memberships` point at the **`jazz`** list (not `classical` — the events are
not classical). It is therefore single-category; **no multi-list membership is
needed** at present.

## List URL(s)

- Roster: `https://www.casabatllo.es/en/magic-nights`
  - 301-redirects to `https://www.casabatllo.es/en/online-tickets/visit-magic-nights/`.
  - Server-rendered (no JS): a `<ul class="artists-list">` of
    `<li class="artists-item">`, one per act. **Carries no dates** — only the
    artist name, its genre string, and a link to the artist's own page.
  - Localized variants exist (`/es/noches-magicas`, `/ca/nits-magiques`); we scrape
    the EN page (titles are artist names — language-neutral).
- Per-artist page (linked from the roster), e.g.
  `https://www.casabatllo.es/en/visit-magic-nights/audrey/`
  - Server-rendered (no JS): a `[data-module="event-artist"]` section with the
    act's dated concert occurrences. **This is where the dates live.**
  - So `scrape()` is 1 (roster) + N (one per artist) requests.

## Data source (server HTML — verified via httpx, not just the rendered DOM)

### Roster page → `parse_agenda(html)` → `[(name, genre, detail_url)]`
| Field        | Source                                              |
|--------------|-----------------------------------------------------|
| name         | `li.artists-item .artist-title label`               |
| genre        | `li.artists-item .artist-title span` (free-text)    |
| detail_url   | `li.artists-item a.artist-content[href]` (abs-ified) |

### Artist page → `parse_artist_events(...)` → one `ScrapedEvent` per occurrence
Occurrences are grouped by month: `ul.cb-events__list__month` with a `<label>`
month name; each `<li class="cb-event-item">` is one concert.

| Field            | Source                                                                                  |
|------------------|-----------------------------------------------------------------------------------------|
| `title`          | the artist name (from the roster)                                                       |
| `start_date`     | month `<label>` + `.event-datetime__date` ("Tuesday 9") → year resolved by weekday (below) |
| `start_time`     | `.event-datetime__hour` ("20:00 h" → 20:00)                                             |
| `source_url`     | the artist page URL                                                                     |
| `external_id`    | `event_id` query param of `li a.cb-btn[href]` (`…select-your-ticket?event_id=16381921`) |
| `category_slugs` | always `["jazz"]` (nearest existing music category — see above)                          |
| `annotations`    | the roster genre string verbatim (e.g. "Jazz, Soul, R&B, Disco")                        |
| `price`          | **None** — see below                                                                    |

### Date / year rule

The page prints the weekday + day-of-month + month name but **no year**
("Tuesday 9", under a `June` label). `_resolve_year` picks the year (this year or
the next two) whose `month/day` actually falls on the stated **weekday** and is
`>= today` — the weekday pins the year unambiguously (more robust than a bare
next-occurrence heuristic across a year boundary). Verified: "Tuesday 9 / June" →
2026-06-09 (a Tuesday); "Friday 21 / August" → 2026-08-21 (a Friday).

### `disable` items

Past/unavailable dates render as `<li class="cb-event-item disable">` with **no
ticket link and no `event_id`** (e.g. La Mercabanda "Tuesday 2", already past on
the 2026-06-02 capture). These are **skipped** (an item with no `event_id` is not a
bookable concert).

### `external_id`

The `event_id` is already **per-occurrence** (a distinct id per concert date), so
it is used directly — no date+time qualification needed (each artist date has its
own id; the Filmoteca collapse trap does not apply). `scrape()` still de-dupes
event_ids across artist pages defensively (the upsert raises on an intra-batch
duplicate).

### price

Magic Nights is a **visit + cava + concert bundle** whose price varies by day/time
(stated in the FAQ "Why are there different prices depending on the day and time?")
and is only revealed inside the ticketing flow. The only € figure on the artist
pages is a **"-20€ residents" discount** (a member/discount tier — skipped per the
price convention). There is no scrape-able flat public price → `price = None`
(not guessed). If a flat price ever surfaces, normalize free-entry phrases to
`"free"` and "sold out" markers to `"sold-out"`.

### ticket status

Each item shows a residents-discount status (`.promo-available` "-20€ residents" /
`.promo-soldout` "Residents discount sold out") alongside `.tickets-available`
("Tickets available"). `promo-soldout` refers to the **residents discount**, not
the concert — it is NOT a sold-out signal and is intentionally ignored.

## Fixtures (offline tests)

- `tests/fixtures/casa_batllo_agenda.html` — the roster page (the "agenda").
- `tests/fixtures/casa_batllo_artist.html` — one artist page (Audrey), needed
  because the dated occurrences live on the artist page, not the roster.

## Quirks

- `/en/magic-nights` 301s to `/en/online-tickets/visit-magic-nights/`; follow
  redirects.
- The roster has 19 acts; "Lexter" and "Nika Mills Trio" currently have **0**
  bookable dates (no occurrences) and "Artist to be defined" is a placeholder act
  (kept — it has a real dated, ticketed occurrence; no genre annotation).
- `event_id` is shared cleanly per concert; no two artist pages reuse one (verified
  live).

## Verification (2026-06-02)

Live scrape: **80 events**, 2026-06-03 → 2026-08-30, across 17 distinct artists.
Coverage: start_time 80/80, category 80/80 (`jazz`), external_id 80/80 (all
unique), annotations 79/80 (the 1 without is the "Artist to be defined"
placeholder, by design); price 0/80 (None — no scrape-able flat price). Field-by-
field cross-check of Audrey's 6 occurrences against the live DOM (month + weekday +
day + time + event_id) — all agree, and the weekday→year resolution lands on the
correct ISO dates. Roster of 19 acts + genres matches the live page.

last verified: 2026-06-02
