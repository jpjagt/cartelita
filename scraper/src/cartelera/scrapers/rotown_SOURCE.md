# Rotown — source map

Venue slug: `rotown` (Rotterdam). Categories **pop, club** (lists `pop`,
`club`, whitelisted). Nieuwe Binnenweg 19 — pop/indie venue + café.

Site: `https://www.rotown.nl/` (WordPress, "Theater for WP"). Client: httpx
with the Cartelita UA. Tickets are sold on Stager — never fetched.

## Requests

1. `GET https://www.rotown.nl/` — the homepage renders the whole upcoming
   programme (~145 cards incl. other venues, featured cards repeated).
2. One show page per **club night** (~15) for the door price.

## Fields (per `.wp_theatre_event_container` card)

| Field | Source |
|---|---|
| `title` | `.wp_theatre_event_title` |
| `start_date`/`start_time` | the card's JSON-LD `startDate` (local, "2026-10-14T20:30"); `23:59` is Rotown's placeholder for a late slot → time None |
| `price` | JSON-LD `offers.price` (online/presale) → "25,50€"; `availability` SoldOut or status "Uitverkocht" → `sold-out`; no offer + "Deurverkoop: €7" → "7€". Club nights: show page `.wp_theatre_event_remark` "Deur: €7,00" → the higher door price |
| `category_slugs` | `.wp_theatre_event_subtitle` == "ROTOWN NIGHTS" (Rotown's club-night series, also its own nav page `/rotown-nights/`) → club; else pop |
| `annotations` | subtitle (series/tour) + support title ("Support: …") |
| `description` | `.wp_theatre_event_sounds_like` ("Voor fans van: …") |
| `image_url` | JSON-LD `image` |
| `source_url` | JSON-LD `url` (`/agenda/<slug>/`) |
| `external_id` | `<slug>@<date>` |

## Exclusions (curation)

- **Shows at other venues** — JSON-LD `location.name != "Rotown"` (~55:
  LantarenVenster, V11, Maassilo, Annabel, Roodkapje West, De Doelen, Theater
  Rotterdam, MONO, Uniek, Kantine Walhalla, Arminius). Their own sources own
  them; the **Maassilo** ones are picked up by `maassilo.py` (Maassilo's own
  agenda lacks them).
- **Free café programme** — cards with status "Gratis entree" and no ticket
  offer: Spelletjesavond, Crafternoon, Open Mic Night, Rock 'N Rommel, Records
  DJs & Drinks, The Official Unofficial (free LotD side festival).

## Quirks

- Left of the Dial festival passes (multi-venue) are listed at Rotown → kept as
  pop, sold-out.

Last verified: 2026-10-14 via HTTP cross-check (5 random show pages: "Deur
open/Start" times and "€ 19,50"-style prices match; found the club-night door
price that the JSON-LD lacks → added the door-price step).
