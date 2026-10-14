# BASIS — source map

Venue slug: `basis-utrecht` (Utrecht). Category **club**; list `club`
(whitelist club). Oudegracht aan de Werf 97 (wharf cellar). Site
`clubbasis.nl` (`basis.club` is a parked domain).

Client: plain httpx with the Cartelita UA; shared `_tribe_events.py`.

## Data source

`https://clubbasis.nl/wp-json/tribe/events/v1/events?per_page=50` (1 page).

| Field | Source |
|---|---|
| `external_id` | event `id` |
| `title` | `title` |
| `start_date`/`start_time` | `start_date` (local; 23:00/23:59 nights) |
| `price` | Tribe cost is empty; the description's ticket block: "/ Early entry before 23:30 €15" · "/ Doorsale entry after 23:30 €20" → the highest €-amount on an entry/doorsale/ticket line (the door price, `"20€"`). None when absent |
| `image_url` | `image.url` |
| `annotations` | `categories[].name` (genres: Hardtechno, Bounce, House, …) minus `Other` |
| `category_slugs` | always `club` |

## Exclusions

- Events whose ONLY category is `Other` (no genre): a free community
  production class. `Other` next to a genre (Le Guess Who? listening session,
  "Experimental") is kept.

## Quirks

- "23:30 €15" — the euro regex must not read the time's minutes as the amount
  (guarded in `_eur.eur_amounts`).

## Verification

Last verified: **2026-10-14 via HTTP cross-check.** Live: 20 events,
2026-10-16 → 2026-12-26; time 20/20, price 18/20. Independent check: first 6
events' detail pages ("Doorsale … €N" regex, title-adjacent time) — 6/6 agree.
