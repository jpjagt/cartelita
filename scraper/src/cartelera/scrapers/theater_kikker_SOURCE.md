# Theater Kikker — source map

Venue slug: `theater-kikker` (Utrecht, Ganzenmarkt 14). Categories theater,
dance, kids. Shared helpers + ownership notes: `cre8ion_SOURCE.md`.

## List URL (httpx, server-rendered)

`https://www.theaterkikker.nl/agenda` — the WHOLE season on one page (~2 MB):
one `div.event.desktop` card per performance (a `div.event.mobile` twin is
ignored). Detail: the card's `a.event-link` (`/agenda/<slug>`), one per
programme, fetched once (≤ 3 concurrent).

## Fields

| Field | Source |
|---|---|
| `title` | `.titel` |
| `start_date` | `.date` "wo 14 oktober" (no year → weekday picks it) |
| `start_time` | `.time` "20:00u" |
| `description` | `.gezelschap` (company) — `.oneliner` |
| `category_slugs` | `.genre` comma list (see mapping) |
| `annotations` | genre labels (minus "Language no problem") + Kikker Kompas themes (`.kikker-kompas .item`) + the detail row's `.date .label`s |
| `language` | `"Language no problem"` when that label is in `.genre` |
| `price` | card `.ticket-wrapper` "Uitverkocht" → `sold-out`; else the detail `.ticket-row.desktop` for that date+time: `.price` "Van € 10,50 tot € 21,00" → `21€` (the low end is the U-pas 50% discount, so the full price, not a range) |
| `image_url` | card `img[src]` |
| `external_id` | `<slug>@YYYY-MM-DDTHHMM` |

## Category mapping (genre labels, never titles)

Theater, Muziektheater, Performance, Storytelling → `theater`; Dans → `dance`;
Jeugd → `kids` (all "2,5+"…"8+" family shows — Herfststukjes, Winterkost,
Lente-Uitjes).

## Exclusions (curation)

- Genre **Verhuur** (rentals: amateur companies, a flamenco rental) — out.
- Rows with no stage genre (only "Specials & festivals": a genealogy workshop,
  a writers' studio) — out.
- Cards with status **Geannuleerd** / **Verplaatst** — out.
- Dates whose detail row carries a **Verhuur** / **Verplaatst** /
  **Geannuleerd** `.label` — out (TussenTijd is "Dans" on the card but each
  date is labelled Verhuur on the detail page). Other row labels (Try-out,
  met nagesprek, extra speeldatum) become annotations.
- Rows whose detail hall isn't **Grote Zaal / Kleine Zaal** ("Kikker op
  Locatie" at Boorstraat 107 = Theater Utrecht, "Op locatie TK" = SSBU,
  ZIMIHC theater Stefanus) — out; those venues own them.

Live 2026-10-14: 202 cards → 182 kept.

## Verification

Last verified: **2026-10-14 via HTTP cross-check** — cards 20–28 re-parsed with
throwaway regexes plus their detail rows (hall, price): 8/8 agree on title,
date, time, category and price (sold-out confirmed against the card button).
Live run: 182 events 2026-10-14 → 2027-05-12; time 182/182, price 180/182 (the
two Le Guess Who? festival days state no price), language 37.
