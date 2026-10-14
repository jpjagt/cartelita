# Roodkapje — source map

Venue slug: `roodkapje` (Rotterdam). Category **alternative** (list
`alternative`). Keileweg 10A (M4H; "Roodkapje West") — artist-run
living-room/project space: DIY gigs, noise, punk, queer nights, exhibitions.

Site: `https://roodkapje.org/` (WordPress/Divi; events are a `stager_event`
post type served on roodkapje.org itself). Client: httpx with the Cartelita UA.

## Requests

1. `GET https://roodkapje.org/agenda/` — "Coming up": `a.rk_event` per event
   with class `rk_event_category_<live|art>`, `.rk_event_dates` ("30 October
   2026"), `.rk_event_title`, `data-thumbnail`.
2. One `/event/<slug>/` page per live event.

## Fields

| Field | Source |
|---|---|
| `start_date` | agenda `.rk_event_dates` (first "D Month YYYY") |
| `start_time` | event page: "Start: 20:30" in `.rk_event_content`, else first HH:MM of `.rk_event_ticket` ("20:30-23:00") |
| `price` | `.rk_event_ticket` text: "sold out" → `sold-out`; amounts ("tickets 15,-", "€10", times stripped) → `eur_price`; else None (tickets on Stager/Rotown) |
| `category_slugs` | `live` → alternative |
| `external_id` | `<slug>@<date>` |

## Exclusions

Items only in Roodkapje's `art` category (exhibitions, open studios,
residency presentations) — not our categories.

Low volume: 3 upcoming shows on 2026-10-14 (the sitemap has ~1200 past events,
so the venue is active; programme is announced a few weeks ahead).

Last verified: 2026-10-14 via HTTP cross-check (all 3 event pages: times,
"tickets 15,-", "sold out" match).
