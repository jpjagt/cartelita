# Baroeg — source map

Venue slug: `baroeg` (Rotterdam). Categories **alternative, club** (lists
`alternative`, `club`, whitelisted). Spinozaweg 300 — metal/punk/hardcore
stage since 1984.

Site: `https://baroeg.nl/` (WordPress, "Theater for WP"). Client: httpx with
the Cartelita UA. One request: `GET https://baroeg.nl/agenda/` (all upcoming
shows, ~30; the REST `wp_theatre_prod` count agrees).

## Fields (per `.wp_theatre_event` card)

| Field | Source |
|---|---|
| `start_date` | `.wp_theatre_event_startdate` "za 17/10/26" (d/m/yy) |
| `start_time` | `.wp_theatre_event_starttime` "22:00" |
| `title`/`source_url` | `.wp_theatre_event_title a` (production page) |
| `price` | `.wp_theatre_event_tickets` "Vvk € 25,00. Entree € 27,50." → amounts after "€" (cut at "Combitickets"), highest (door) price; "uitverkocht" → `sold-out` |
| `category_slugs` | Baroeg's genre list `.wpt_production_category`: "dance night" / "Nachtprogramma" (gabber/speedcore nights) → club; else alternative |
| `annotations` | the other genre labels ("death", "black", "doom", "punk", …) |
| `description` | `.wp_theatre_prod_excerpt` |
| `image_url` | the card's thumbnail |
| `external_id` | `<production slug>@<date>` |

## Exclusions

- Cancelled shows: tickets status `.wp_theatre_event_tickets_status_cancelled`
  ("Geannuleerd").
- "Baroeg On Tour @ <venue>" shows (Baroeg's own series for shows it books
  elsewhere, e.g. SoundVille, Roodkapje) — the card still says venue
  "Baroeg", so the series name in the title is the only signal.

Category choice: everything live is `alternative` (Baroeg's whole programme
is underground metal/punk/hardcore/darkwave); `rock` was considered but
Baroeg has no rock-vs-other discriminator beyond fine-grained genres.

Last verified: 2026-10-14 via HTTP cross-check (5 production pages: time,
"Vvk/Entree" amounts and title match).
