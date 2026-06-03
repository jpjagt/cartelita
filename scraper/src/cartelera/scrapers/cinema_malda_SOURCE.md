# Cinema Maldà — source map

Venue slug: `cinema_malda`. Independent cinema in Barcelona's Gothic Quarter.
Single-category venue: **film** (every session is a film screening; VOSE/VOSCAT
original-version programming). Spanish (es) site.

## List URL(s)

- **Day-by-day schedule (authoritative):**
  `https://www.cinemamalda.com/cartelera-dia-dia/`
  This is the clean, structured weekly schedule and the source of truth for
  date + time + title. One request covers the whole current week.
- Homepage (`https://www.cinemamalda.com/`) carries the same week as a grid of
  `.movies a.movie` cards (title in `h3`, detail link in `href`, poster image),
  but its per-card showtimes are inconsistent free text ("Próximamente",
  "5, 6 y 7/6", "Ma 2", …) — NOT used for the schedule. We DO scrape it once to
  build a `slug set` for validating per-film detail URLs (see source_url).
- Prices: `https://www.cinemamalda.com/precios-cine-malda-barcelona-preus/`
  (read once; per-weekday general price — see below).

Do NOT use the femraval.com directory link.

## Data source (server-rendered HTML — no JS needed)

The day-by-day page renders inside `.entry-content .sinopsi`:

- An `<h2>` header: `CARTELERA DEL 29 AL 4 DE JUNIO DE 2026` — gives the
  **month + year** context for the week (and the closing day/month).
- One `<p>` per calendar day. Each `<p>` opens with an orange day heading
  `span[style*="#ff6600"] > strong` like `MARTES 2` / `MIÉRCOLES 3`
  (Spanish weekday name + day-of-month), then `<br/>`-separated session lines:
  `HH:MMh – TITLE (VO…)`  e.g. `16:15h – TRES ADIOSES (VOSE)`.

Per session line:

| Field            | Source                                                                     |
|------------------|----------------------------------------------------------------------------|
| `start_time`     | the `HH:MMh` prefix → `dt.time`                                             |
| `title`          | text after `–`, original-version tag like `(VOSE)`/`(VOE)`/`(VOSCAT)` kept  |
| `start_date`     | day-of-month from the day heading + month/year from the `<h2>` header       |
| `source_url`     | film slug = slugify(title minus parenthetical tags); validated against the homepage slug set → `https://www.cinemamalda.com/<slug>/`. If not found, falls back to the day-by-day page URL. |
| `external_id`    | `<slug>@<date>T<HHMM>` — slug qualified by the occurrence (Filmoteca trap)  |
| `category_slugs` | always `["film"]`                                                           |
| `price`          | per-weekday general price (below)                                           |
| `image_url`      | poster from the matching homepage card (by slug), if available             |
| `annotations`    | the VO tag (e.g. "VOSE") captured as a free-form annotation                |

### Date rule

The `<h2>` header `… DEL <d1> AL <d2> DE <MONTH> DE <YEAR>` provides MONTH+YEAR.
Each day heading gives the day-of-month; the full date is
`date(year, month, day)`. If a week straddles a month boundary, the header's
closing month (`d2`'s month, when two months are named) is used for days whose
number is small (≤ the opening day it would otherwise precede) — i.e. month is
rolled forward when the day-of-month wraps. Spanish month names are mapped
es→number; weekday names in the heading are ignored (the day-of-month is
authoritative).

### Price (per weekday, read once from the prices page)

The prices page lists a flat **per-day** admission (one ticket = all films that
day). It varies by weekday:
- Mon / Wed ("día del espectador/a"): **5,90€**
- Tue / Thu / Fri: **7,50€**
- Sat / Sun / holidays: **9€**

Parsed from the prices-page rows (weekday label → `N[,N]€`) into a weekday→price
map and applied per screening by `start_date.weekday()`. Normalized to a concise
display string (comma→dot, "€" kept). Falls back to the range `"5,90–9€"` if the
prices page can't be parsed. Sunday is treated as Sat/holiday tier (9€); the page
lists FESTIVOS rather than DOMINGO explicitly.

## external_id

`<film-slug>@YYYY-MM-DDTHHMM`. The film slug alone is shared across every
screening of a film (same film screens many days), and the upsert dedups on
`(venue, external_id)` — a bare slug would collapse occurrences (Filmoteca trap).
Qualified with the occurrence date+time. `source_url` stays the bare film page.

## i18n

Site is Spanish only; titles carry the original-version tag. No translations
emitted.

## Quirks

- The homepage card grid includes non-film cards ("Tarifas"/precios,
  "cartelera-dia-dia" banner) — ignored (we only read it for the slug set/images).
- Day-by-day session lines may carry a trailing `(ESTRENO)` / `(NO ENTRA A LA
  SESSIÓ CONTINUA …)` note. Title is the part between the time and the first
  parenthetical; the VO tag is captured as an annotation; other notes are dropped.
- Tickets are box-office only ("Venta de entradas solo en taquilla. No tenemos
  venta online") — there's no per-session sold-out signal to scrape.
- The day-by-day page covers only the current week (~Tue–Sun; films change weekly).

## Verification (last verified: 2026-06-01)

Live `dry-run cinema_malda` → 12 events for the week of 29 May–4 Jun 2026
(Tue 2 / Wed 3 / Thu 4). 100% coverage: start_time, price, image_url,
annotations, external_id; categories `{film: 12}`. Cross-checked field-by-field
against the live day-by-day page:
- MARTES 2 → 16:15 Tres adioses, 18:20 Conoce a los bárbaros, 20:15 El drama (7,50€ Tue tier)
- MIÉRCOLES 3 → 11:30 El amigo silencioso, 14:00 Todo lo que fuimos, 16:30 Conoce,
  18:15 El drama, 20:15 Uyariy (5,90€ Wed "día del espectador")
- JUEVES 4 → 14:35 Un poeta, 16:45 Hangar rojo, 18:15 El drama, 20:00 Conoce (7,50€ Thu tier)
All source_urls resolved to real /<slug>/ detail pages (verified HTTP 200).
Recurring films (El drama ×3, Conoce a los bárbaros ×3) carry distinct
external_ids — no occurrence collapse.

last verified: 2026-06-01
