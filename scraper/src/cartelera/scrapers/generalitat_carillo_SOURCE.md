# Palau de la Generalitat — Carilló del Palau — scraper source map

Last verified against live site: 2026-06-02.

**Venue:** Carilló del Palau — the carillon (bell) of the Palau de la Generalitat
de Catalunya, Plaça de Sant Jaume, Barri Gòtic, Barcelona. Free public carillon
concerts; the bells are heard from the Pati dels Tarongers / Galeria Gòtica
(audience inside, by prior registration) and from the streets of the Barri Gòtic.
**Categories produced:** `classical` only (carillon / bell concerts — classical
and popular programmes).

## Source

- **Single list URL:** `https://presidencia.gencat.cat/ca/carillo`
  (302 → canonical `https://web.gencat.cat/ca/generalitat/qui-som/seus-govern/palau-generalitat/carillo-del-palau`).
  Plain server-rendered HTML (Adobe AEM). No event JSON-LD, no JSON blob — the
  concert dates live in two prose-ish content blocks parsed from the rendered DOM.
- The page describes the general cadence in prose ("un concert cada primer
  diumenge de mes, a les 12 del migdia, excepte agost i setembre", plus Mercè and
  Sant Esteve), but the **actual upcoming dates are listed discretely** in two
  places, so we parse those discrete listings rather than synthesising the
  recurrence:
  1. **Temporada "Pròxims concerts"** — `div.highlighted-content` whose
     `h2.section-heading__title` is `Temporada 20xx-20xx`, an inner `<ul><li>`
     list. Each `<li>` = one monthly concert.
  2. **Festival programme** — `div.highlighted-content` whose
     `h2.section-heading__title` contains `Festival Internacional de Carilló`.
     A `Dates:` line gives the day numbers + year; a `Programa` paragraph has one
     `<b>` day header (e.g. `Divendres 17 de juliol`) per festival concert.
- The full season is only in a linked PDF
  (`Temporada_Concerts_Carillo_..._.pdf`) — intentionally NOT chased; we take the
  discrete "Pròxims concerts" list on the page.

## Per-field mapping

### Temporada "Pròxims concerts" `<li>` items

| Field | Source |
| --- | --- |
| month | first `<b>` in the `<li>` (Catalan month name → month number). |
| day | second `<b>` in the `<li>` — `diumenge 7`, `diumenge 5,` etc.; the integer. |
| year | inferred from the month vs. today (so a Dec→Jan list rolls to next year). |
| start_time | a clock value in the `<li>` text (`a les 12h`, `a les 12 h`) → time; default 12:00 if absent (the venue's standard midday slot). |
| title | `Concert de Carilló del Palau` + the `<a.link>` programme name if present (e.g. `The Beatles and 49 bells`). |
| description | the free-text remainder of the `<li>` (the programme blurb). |
| price | `free` (entry is always free — "L'entrada és gratuïta"). |
| source_url | the carillon page URL. |
| external_id | `generalitat-carillo-<ISO date>` (one occurrence per date). |
| annotations | `Temporada <season>` + the programme name. |

### Festival programme `<p>` (`<b>` day headers)

| Field | Source |
| --- | --- |
| year | from the `Dates:` line (`... de juliol de 2026`). |
| day / month | each `<b>` day header in the `Programa` `<p>` (`Divendres 17 de juliol`). |
| start_time | the `Hora:` line (`21:00 h`) → 21:00. |
| title | `Festival Internacional de Carilló` + the `<i>` programme title. |
| description | the `<i>` programme title + the carillonist sentence following it. |
| price | `free`. |
| source_url | the carillon page URL. |
| external_id | `generalitat-carillo-festival-<ISO date>`. |
| annotations | the festival edition heading + carillonist. |

## Category discriminator

There is none — every carillon concert is `classical`. (Programmes range from
Mozart to The Beatles, but the instrument/format is classical recital; the
programme genre goes into `annotations`, not a top-level category.)

## external_id / dedup

One row per occurrence (per date). Festival and Temporada ids are namespaced
(`...-festival-<date>` vs `...-<date>`) so a Sunday that appears in both blocks
would not collide — in practice they don't overlap. Per-occurrence id, so the
upsert keeps each date as its own Event.

## Dates: discrete vs recurring

The page states a **recurring cadence** (first Sunday of each month at 12:00,
except Aug/Sep; July festival; Mercè + Sant Esteve extras) but also lists the
**concrete upcoming dates discretely** ("Pròxims concerts" + the festival
programme). We parse the **discrete listed dates** — typically only the next
1–3 months of monthly concerts plus the (annual, July) festival's 6 dates. So
the scrape yields a small handful of events, not a year of synthesised
recurrences. The complete season is in a PDF we do not parse.

## Verification (2026-06-02)

- `parse_agenda` on the saved fixture: 8 events — 2 monthly (June 7, July 5,
  both 12:00) + 6 festival (17/18/19/24/25/26 July, all 21:00). Coverage:
  price 100% (`free`), category 100% (`classical`), start_time 100%,
  date/title/url 100%. Weekday labels cross-checked against the calendar
  (17 Jul 2026 = Friday … 26 Jul = Sunday; 7 Jun & 5 Jul = Sunday) — all match.
- Browser daemon was flaky during this pass; verified via the saved live HTML
  (httpx, follow_redirects) which is the exact bytes the scraper fetches.

## Quirks

- The carillon page redirects `presidencia.gencat.cat/ca/carillo` →
  `web.gencat.cat/...`; the scraper uses the short URL with `follow_redirects`.
- A `User-Agent` header is sent (the site returns the full page without it too,
  but UA is set defensively).
- Catalan month/day-name parsing (`juny`, `juliol`, `diumenge`, etc.).
- If the page ever drops the discrete "Pròxims concerts" list and exposes only
  the PDF, this scraper would yield only the festival (or nothing) — that's the
  bounded-effort tradeoff; chasing the PDF was out of scope.

## Seed requirements

- **venue slug:** `generalitat-carillo`
- **display name:** `Carilló del Palau de la Generalitat`
- **address:** `Plaça de Sant Jaume, s/n, 08002 Barcelona`
- **site_url:** `https://presidencia.gencat.cat/ca/carillo`
- **category slugs produced:** `classical`.
- **list membership:** `classical` (NULL whitelist — single-category venue, all
  events are classical).
