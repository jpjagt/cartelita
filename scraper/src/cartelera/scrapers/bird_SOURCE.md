# BIRD — source map

Venue slug: `bird` (Rotterdam). Categories **jazz, pop, club** (lists `jazz`,
`pop`, `club`, each whitelisted to its category). Raampoortstraat 24-28 —
jazz-rooted concert stage, club nights, restaurant (Mavis).

Site: `https://www.bird-rotterdam.nl/` (Next.js) fed by a **public Prismic
repository** `bird-rotterdam`; we read the Prismic documents API, not HTML.
Client: httpx with the Cartelita UA (`http.CARTELITA_COMPAT_UA`).

## Requests

1. `GET https://bird-rotterdam.cdn.prismic.io/api/v2` → master `ref`.
2. `GET …/api/v2/documents/search?ref=<ref>&lang=nl-nl&pageSize=100&page=N`
   `&q=[[at(document.type,"agenda")][date.after(my.agenda.event_date,"<yesterday>")]]`
   `&orderings=[my.agenda.event_date]&fetchLinks=genres.title,main_category.title`
   (paged by `total_pages`; ~70 docs → 1 page).

## Fields (one `agenda` document = one occurrence)

| Field | Source |
|---|---|
| `title` | `data.title` (rich text) |
| `start_date` | `data.event_date` (UTC) → Europe/Amsterdam |
| `start_time` | `data.times` free text: the time after `start`/`aanvang`/`concert` ("Start 20:30 \| Doors 19:30", "talk 19:00 \| concert 20:30"), else its first HH:MM ("23:00 - 04:00"), else local `event_date` time |
| `price` | `data.price` free text ("V.A. €14,95", "€28 - €45", "GRATIS", "UITVERKOCHT") → `eur_price` (highest unless ≥2× spread); `ticket_state` "SOLD OUT" → `sold-out`; "Gratis" → `free` |
| `category_slugs` | `data.main_categories[].main_category.uid`: `club` → club; `live` → **jazz** if BIRD's own genre `jazz` is tagged, else **pop** |
| `annotations` | `data.top_title` (series, e.g. "BIRDsessions") + genre titles (via `fetchLinks`) |
| `description` | `data.meta_description` |
| `image_url` | `data.cover_image.url` |
| `source_url` | `https://www.bird-rotterdam.nl/event/<uid>/` |
| `external_id` | Prismic document id |

## Exclusions (curation)

- **`mavis` main category** — "Pass da Jazz – Elke Vrijdag bij Mavis": the free
  weekly session in BIRD's restaurant (Mavis has `is_displayed_in_event_page:
  false`). A recurring bar night, not programme. Also `food`/`garden`-only docs.
- **Shows BIRD (co-)presents at other venues** (~17 of ~40 live shows:
  LantarenVenster, De Doelen, Annabel, Maassilo, V11): `top_title`/`subtitle`
  starting "At …" ("At LantarenVenster", "AT MAASSILO"), uid `-at-<venue>`, or
  the description's "Let op: dit concert vindt plaats bij …, en niet bij BIRD".
  Those venues own their listings (Annabel's site lists its BIRD x Annabel
  shows; LantarenVenster/De Doelen are batch 4; V11 is not covered).

## Quirks

- `event_date` is the start in UTC; for concerts it equals "Start", for club
  nights the opening time.
- Genre uids are inconsistent (`carribean`/`caribbean`, `rb`/`rnb`); only
  `jazz` is used as a discriminator.
- An EN translation of each doc exists (`alternate_languages`); not used —
  titles are identical.

Last verified: 2026-10-14 via HTTP cross-check (5 random events: the site's
event pages show the same time range, "V.A. €…" price and title).
