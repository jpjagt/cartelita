# Cinemes Texas / Espai Texas — source map

Venue slug: `espai_texas`. Single-category venue for our purposes: **film**
(cinema screenings). Espai Texas is an independent cinema + theatre + bar in
Gràcia, Barcelona; films are screened in Catalan (dubbed/subtitled, `vosc`/`vo`).

## List URL(s)

- Homepage: `https://espaitexas.cat/` — **this is the complete source.** It
  server-renders a full-year calendar widget (one `div.swiper-slide#month_N` per
  month, all months present in one request, no JS / no pagination needed).
- `https://espaitexas.cat/cartellera-cinema/` is NOT a list — it is a single
  featured film page ("destacat") plus a few "altres sessions" teasers. Do not
  use it; the homepage calendar is the real, complete listing.

## Data source (server-rendered HTML — no JS needed)

The calendar renders each calendar day as `div.day[id="day_YYYY-MM-DD"]`; days
with programming also have class `have-events` and contain
`.events-items > a.event`. Each `a.event` is one session/occurrence.

The anchor's classes are the **category discriminator**:

| Anchor class            | Meaning            | We keep? |
|-------------------------|--------------------|----------|
| `a.event.pelicula`      | cinema screening   | **yes**  |
| `a.event.espectacle`    | theatre show       | no       |
| `a.event.activitat`     | activity/event     | no       |

We select only `div.day a.event.pelicula`.

Per `a.event.pelicula`:

| Field          | Source                                                                 |
|----------------|------------------------------------------------------------------------|
| `start_date`   | enclosing `div.day` `id="day_YYYY-MM-DD"` (authoritative)              |
| `title`        | `.event-title` text (venue renders titles ALL-CAPS — preserved as-is)  |
| `start_time`   | `.event-time` text (`"16:00"`); **`"00:00"` ⇒ time unknown ⇒ None**     |
| `source_url`   | the anchor `href` (see below)                                          |
| `external_id`  | per-occurrence: `<href-slug-or-pelicula-slug>@YYYY-MM-DDTHHMM`         |
| `category_slugs` | always `["film"]`                                                    |
| `price`        | day-of-week rule (see below) — calendar carries no price              |

### source_url / href

The anchor `href` is one of two kinds:
- a **koobin booking URL** (`https://espaitexas.koobin.cat/ca/<slug>-[vo|vosc-]YYYYMMDD-HHMM`)
  — present when the session is bookable (18/20 in the 2026-06-01 fixture);
- a venue **detail page** (`https://espaitexas.cat/pelicula/<slug>/`) — present
  when the session is not yet bookable (the 2 sessions with time `00:00`).

We use the anchor `href` directly as `source_url`. The koobin host is reached
*only* via the venue's own page (it is the venue's ticketing subdomain), so this
is not chasing a third-party aggregator. NOTE: the koobin slug does NOT always
equal the `/pelicula/` detail slug (e.g. koobin `lamic-silencios` vs detail
`silent-friend`), so do not try to derive the detail URL from the koobin slug.

### external_id (per-OCCURRENCE)

The same film screens on several days (and koobin slugs for a film can carry a
`-0000` placeholder time, so the slug alone is NOT per-occurrence unique within a
film). We key the occurrence as `<slug>@YYYY-MM-DDTHHMM`, where `<slug>` is the
href's last path segment with any trailing `-[vo|vosc-]YYYYMMDD-HHMM` /
`/pelicula/<slug>/` reduced to the film slug, and the date+time come from the
authoritative `day_` id and `.event-time`. This avoids the Filmoteca trap
(coarse id collapsing occurrences under the upsert's `(venue, external_id)`
dedup, which now raises on in-batch duplicates).

### price

The calendar carries no price. Cinema price is **day-of-week** based, published on
`/informacio-practica/` ("diferents preus: 6€ de dilluns a divendres, 4€ pels
dijous (dia de l'espectador) i 8€ els caps de setmana"):

- Thursday → `"4€"` (dia de l'espectador)
- Saturday / Sunday → `"8€"` (cap de setmana)
- Mon/Tue/Wed/Fri → `"6€"`

(The +1€ online "despesa de gestió" surcharge is a booking fee, not the ticket
price, so it is excluded.) Free-phrase normalization (e.g. "Entrada gratuïta")
is handled defensively if a session ever carries explicit price text, but the
calendar currently never does.

## i18n

Catalan site (`/`); a Spanish mirror exists at `/es/`. Titles in the calendar are
already the canonical Catalan exhibition titles (often bilingual, e.g.
"L'AMIC SILENCIOS (SILENT FRIEND)"). We scrape only the `ca` homepage and emit no
translations — the calendar row is a complete event on its own.

## Quirks

- `cartellera-cinema/` page is a single featured film, NOT the list. Use `/`.
- Titles are ALL-CAPS in the source (house style) — preserved verbatim.
- Sessions with `.event-time == "00:00"` are not-yet-scheduled placeholders;
  time → None, href is the `/pelicula/` detail page.
- The calendar mixes cinema (`pelicula`), theatre (`espectacle`) and activities
  (`activitat`); only `pelicula` is cinema. Filter by class.
- One homepage request covers the whole year; no week/month stepping needed.

last verified: 2026-06-01
