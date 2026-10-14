# WORM — source map

Venue slug: `worm` (Rotterdam). Categories **alternative, film, club** (lists
whitelisted to each). Boomgaardsstraat 71 — avant-garde/underground concerts,
club nights, cinema, performance.

Site: `https://worm.org/` (WordPress, "Theater for WP" productions under
`/production/`). Client: httpx with the Cartelita UA.

## Requests

1. `GET https://worm.org/agenda/` — all upcoming items (~35).
2. One `/production/<slug>/` page per kept item (~20) for the start time.

## Fields

| Field | Source |
|---|---|
| `title` | `.agenda-item__title__title` |
| `start_date` | `.agenda-item__title__date` "Wed 14 October" + year from the preceding `.agenda__month__month` header ("October 2026"); the production page's `.agenda-single-meta__date` ("Wed 14 October 2026") wins when fetched |
| `start_time` | production page `.agenda-single-meta__start` "Start → 20:30" |
| `category_slugs` | WORM's own label `.agenda-item__title__cat`: FIlm → film; Club → club; Concert / Theatre / Performance / Festival → alternative |
| `annotations` | the label, for alternative items |
| `image_url` | `.agenda-item__thumbnail img` |
| `external_id` | `<production slug>@<date>` |
| `price` | None — only on Stager (bots disallowed) |

## Exclusions (curation)

WORM labels Community (sewing/drawing clubs, Art-Gang), Workshop (Singing
Club), Talk, Broadcast / Stream (radio) and Art & expo — not programme for our
categories → left out. An unknown new label is skipped with a warning.

Last verified: 2026-10-14 via HTTP cross-check (5 production pages: full date
and "Start →" time match).
