# De Helling — source map

Venue slug: `de-helling` (Utrecht). Categories **pop**, **club**; lists `pop`
(whitelist pop) and `club` (whitelist club). Helling 7, Rotsoord.

Client: plain httpx (`http.fetch`) with the Cartelita UA (`_eur.HEADERS`).

## List URLs

- `https://dehelling.nl/agenda/` — one server-rendered page with every
  upcoming event (≈65, ~1 year ahead). No pagination.
- `https://dehelling.nl/agenda/?label[]=club` — the venue's own "type" filter
  (server-side), used as the category discriminator.
- `https://dehelling.nl/agenda/?label[]=cafe` — café nights; left out.
- Detail page `/agenda/<slug>-DD-MM-YYYY/` — fetched only for cards without a
  JSON-LD price (free events; ≈5).

## Fields (per `.c-event-card[id]`, embedded `script[type=application/ld+json]`)

| Field | Source |
|---|---|
| `external_id` | card `id` (= URL slug incl. date — one per occurrence) |
| `title` | JSON-LD `name` (HTML-unescaped) |
| `start_date`/`start_time` | JSON-LD `startDate` ("YYYY-MM-DD HH:MM:SS", local) = the detail page's "Aanvang" (the card's "19:30 - 23:00" is doors) |
| `price` | JSON-LD `offers.price` → `"19,50€"`; `eventStatus == "Uitverkocht"` → `"sold-out"`; no price → detail page "Prijs" field ("Gratis" → `"free"`) |
| `image_url` | JSON-LD `image` |
| `annotations` | `.c-event-card__meta li` after the first two (date, door–end time): the venue's genre tags |
| `category_slugs` | card id on the `label[]=club` page → `club`, else `pop` |

Type labels on the site: club, concert, open, cross-over, festival, anders,
cafe. club → club; concert/open/festival/cross-over/anders → pop.

## Exclusions

- `eventStatus == "Afgelast"` (cancelled) — dropped.
- Cards on the `label[]=cafe` filter (café/bar nights) — none at last check.

## Quirks

- **`offers.availability` is unreliable**: it says `SoldOut` for ~20 events
  that are on sale (detail page shows a live "Tickets" button, e.g. Ozric
  Tentacles, GETiKT). Only `eventStatus "Uitverkocht"` means sold out (matches
  the detail page's "uitverkocht" button).
- Tickets are sold on Stager (`dehelling.stager.co`) — never fetched.
- The single "cross-over" item that isn't also club (International Burlesque
  Circus) lands under pop.

## Verification

Last verified: **2026-10-14 via HTTP cross-check.** Live: 65 events,
2026-10-14 → 2027-09-25; time 65/65, price 63/65 (none: Le Guess Who? day
tickets sold by the festival), 16 club / 49 pop. Independent check: first 8
events' detail pages ("Aanvang", "Prijs", "uitverkocht") — 8/8 agree on time
and price.
