# Theater Utrecht — source map

Venue slug: `theater-utrecht` (Utrecht, Boorstraat 107 — the company's own
house, "Centre for Performing Arts"). Category theater. Shared helpers:
`cre8ion_SOURCE.md`.

## Data source (httpx, JSON)

The Nuxt site (`/nl/agenda`) is server-rendered from a cre8ion back-end the
browser also calls directly (`config.public.apiBase` =
`https://www.theaterutrecht.nl/prod`):

```
POST https://www.theaterutrecht.nl/prod/nl/api/events/programs
{"filters": {"startAt": "YYYY-MM-DDT00:00:00"},
 "pagination": {"page": N, "pageSize": 100},   # 100 is the server max
 "sortings": []}
→ {"events": [...], "pagination": {"count", "page", "pages", "pageSize"}}
```

One item per PERFORMANCE: the event fields plus `program` (`id`, `startAt`,
`isCanceled`, `button.text`, `location.name` = city, `attributes` with
`type.name == "Theater"` = the theatre and `"Type"` = In huis / Try-out /
Première / Schoolvoorstelling). ~120 upcoming, 2 pages. The same call on
`/prod/en/api/...` gives the English titles/URLs (matched by `program.id`).
Tickets are sold on Stager, which we never fetch (robots.txt disallows bots).

## Fields

| Field | Source |
|---|---|
| `title`, `source_url` | `title`, `url` (`/nl/agenda/<slug>`) |
| `start_date`/`start_time` | `program.startAt` (00:00 = no time) |
| `description` | `subTitle` (company / series, e.g. "TU FEST") — `fields.extraSubtitle` |
| `price` | `program.button.text` "Uitverkocht" → `sold-out`; else amounts in the free-text `oneLiner` ("Zaterdag 17 oktober | 15:30 | Studio 3 | €10 / €7,50") → highest (the lower ones are reductions); "Free entrance" → `free`; otherwise None (TU's own productions state no price outside Stager) |
| `annotations` | performance Type attributes except In huis (Try-out, Première) |
| `translations` | `en`: title + `/en/agenda/...` URL from the en response |
| `image_url` | `image1.url` |
| `external_id` | `program.id` (per performance) |

## Filtering

- Only performances whose `program` Theater attribute is **Theater Utrecht**:
  national/international tour dates are out, and so are its Utrecht dates at
  Stadsschouwburg Utrecht and Theater Kikker (those venues own them).
- `program.isCanceled`, event Type **Expositie**, performance Type
  **Schoolvoorstelling** — out.
- Category: always `theater` — the API's `genres` list is empty for every
  item, so there is no structural signal for dance or kids.

Curation caveat: the in-house programme also carries TU FEST side items (a
voguing workshop, an ecstatic-dance session, a reading hour for toddlers), a
theatre lecture and Le Guess Who?'s Sound & Culture Summit. The API gives
them the same type ("In huis") and no genre, so they are **kept** (we don't
filter on title keywords).

Live 2026-10-14: 121 upcoming performances → 26 kept.

## Verification

Last verified: **2026-10-14 via HTTP cross-check** — the server-rendered
`/nl/agenda` HTML (`.OverviewListItem`: date, time, title, type, "Utrecht |
Theater Utrecht", button) re-parsed with throwaway regexes: 26/26 in-house rows
match the scraper's events (date, time, title; sold-out/free agree with the
button). Coverage: time 26/26, price 20/26 (Time Machine, Woyzeck: no price
outside Stager).
