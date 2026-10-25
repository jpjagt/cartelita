# PizzaExpress Live — source map

Multi-venue source `pizzaexpress-live` (city `london`, category `jazz`),
today whitelisting one room: **PizzaExpress Jazz Club Soho**
(`pizzaexpress-jazz-club-soho`, 10 Dean Street W1D 3RW — the basement club
running since 1969).

## Data: the site's own JSON API

`GET https://api.pizzaexpresslive.com/products/search-event-information?page=N`
— the back-end of the Next.js site, no auth, hydra collection (30 items a
page, `hydra:view.hydra:next` until the last page; 11 pages / 321 items on
24 Oct 2026). Client: `httpx` with `CARTELITA_COMPAT_UA`. robots.txt
(www) disallows only account/basket/checkout/search/review paths; the API
host has none.

| Field | Source |
|---|---|
| room | `location`: "Soho" / "Holborn" / "Chelsea" / "Leicester Square" → `LOCATIONS` whitelist |
| `title` | `name` |
| `start_date` | `eventDate` "Saturday 24th October" — **no year**: the year (this/next) where that date is the stated weekday, not before today − 7 days |
| `start_time` | `showStartTime` "8:00PM" (show, not doors) |
| `annotations` | `doorsOpenTime` → "Doors 6:30PM" |
| `price` | `price` in pence → `format_gbp` (0 → `free`); `seatAvailable == 0` → `sold-out` |
| `image_url` | `imageUri` |
| `description` | `description` (empty for ~95%) |
| `source_url` | `https://www.pizzaexpresslive.com/whats-on/{slug}` |
| `external_id` | `eventSku` — the per-occurrence product variant (the `slug` is shared by a run: Acoustic Alchemy ×12) |

Events before today (Europe/London) are dropped (the API keeps yesterday's).

## Curation (the API's own `location` field — never titles)

- **Soho — kept.** The jazz club: straight-ahead, Latin, vocal and big-band
  jazz with some soul/funk headliners (Shakatak, Courtney Pine).
- **Holborn — excluded.** Tribute- and soul-led (Fleetwood Bac, The Brit
  Funk Association, Peter White), not a jazz-for-locals programme.
- **Chelsea — excluded.** Singer-songwriter / soul / cabaret ("The Rat
  Pack").
- **Leicester Square — excluded.** The free "Piano Lounge" in a restaurant.

Any other location is logged as `rooms not in the whitelist (review)`.
jazzlondonlive lists Soho and Holborn too; both are in its `EXCLUDED` so this
source is their only owner.

## Verification

Last verified: **2026-10-24 via HTTP cross-check.** Live: 154 Soho events
(24 Oct 2026 → 28 Apr 2027) of 321; price 154/154 (12 sold-out). Independent
check against the venue site's own event pages (`/whats-on/{slug}`,
`__NEXT_DATA__.props.pageProps.event.childEvents`, not the search API):
Jazz Dynamos 25 Oct 13:00 £28 isSoldOut=true → ours `sold-out`; Joanna Eden
Band 25 Oct 20:00 £25, Paula Morelenbaum 26 Oct 20:00 £23, Chiminyo NRG 5
27 Oct 20:00 £20 → ours identical; venue "PizzaExpress Jazz Club (Soho)";
Acoustic Alchemy's 12 child events (14–23 Dec, incl. 19 Dec 18:00 + 21:00,
20 Dec 13:00 + 20:00) == our 12 occurrences.
