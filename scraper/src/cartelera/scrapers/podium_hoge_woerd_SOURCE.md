# Podium Hoge Woerd — source map

Venue slug: `podium-hoge-woerd` (Utrecht — De Meern / Leidsche Rijn). Categories
theater, dance, kids, pop. Shared helpers + ownership notes: `cre8ion_SOURCE.md`.

## List URLs (httpx, server-rendered)

`https://www.podiumhogewoerd.nl/agenda?StartDate=DD-MM-YYYY` — 10
`div.event.desktop` cards per page. The site's "load more" calls
`/mvc/event/partial?p=N`, which **robots.txt disallows**, so we page with the
agenda's own date filter instead: start today, then restart at the last date
on the page (its rows may continue), until a page has < 10 cards (≈14 pages).
Overlapping rows dedupe on `external_id`. Detail: `/agenda/<slug>`, once per
programme.

## Fields

| Field | Source |
|---|---|
| card spans | `.info-wrapper a` has three bare spans: genre list, company (`.titel`!), show title |
| `title` | third span |
| `description` | company (second span) |
| `start_date`/`start_time` | `.date` "do 15 oktober" (no year → weekday) / `.time` "20:00u" |
| `category_slugs` | genre list (see mapping) |
| `annotations` | genres (minus "No Dutch? No Problem!") + `.labels .tag` (Try-out, Met inleiding, Wat speelt er?, Jong Podium Approved, …) + detail row labels |
| `language` | `"No Dutch? No Problem!"` when in the genre list |
| `price` | card "Uitverkocht" → `sold-out`; else detail `.ticket-row.desktop` `.price` ("Prijs Van € 10,50 tot € 21,00" → `21€`; the low end is the U-pas 50% discount, see /je-bezoek/ticketinformatie) |
| `external_id` | `<slug>@YYYY-MM-DDTHHMM` |

## Category mapping (genre labels, never titles)

Theater, Cabaret, Kleinkunst, Muziektheater, Circustheater, Theatertour (a
touring-show label, not backstage tours), Verrassing (Nationaal
Theaterweekend mystery show) → `theater`; Dans → `dance`; Jeugd → `kids`;
Muziek → `pop` only without a stage genre (tribute bands, singer-songwriters,
Lavinia Meijer).

## Exclusions (curation)

- Genres **Talks** (lecture series), **Workshop**, **Verhuur** (rentals — e.g.
  a local harmony orchestra's new-year concert) — out, whatever else tagged.
- Cancelled (`Geannuleerd` button or label) — out; likewise a date whose
  detail row is labelled Verhuur / Verplaatst / Geannuleerd (shared rule).

Live 2026-10-14: 119 cards → 105 kept (9 talks, 3 rentals, 1 workshop, 1
cancelled). Mainstream touring cabaret is kept (27 Cabaret rows).

## Verification

Last verified: **2026-10-14 via HTTP cross-check** — the `StartDate=01-12-2026`
page re-parsed with throwaway regexes + detail price rows: 6/6 programme rows
agree (title/date/time/price/category; sold-out confirmed against the card
button), the 7th is a Talk, excluded by design. Live run: 105 events
2026-10-15 → 2027-04-30; time, price 105/105; language 16.
