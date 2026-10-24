# DICE London venues (`dice_london.py` + shared `_dice.py`) — source map

22 London gig/club venues, **one source per venue** (source slug = venue
slug, per-venue health), all on DICE (dice.fm). Venue table, DICE names and
category mapping: `dice_london.py`.

## Two ways in

| Mode | Venues | Request | What it gives |
|---|---|---|---|
| **Venue's own widget key** | MOTH Club (key published in mothclub.co.uk's page script, `DICE_KEY`), Strongroom (`apiKey` in strongroombar.com's DICE widget config) | `GET https://partners-endpoint.dice.fm/api/v2/events?page[size]=100&page[number]=N&filter[venues][]=<DICE venue name>` with `x-api-key: <that venue's key>` | every upcoming event: `name`, `date` (UTC) + `timezone`, `type_tags`, `genre_tags`, `ticket_types[].price.total` (pence, incl. fees), `sold_out`, `status`, `hash`+`perm_name`, `raw_description`, `event_images` |
| **Public pages** | the other 20 | `GET https://dice.fm/venue/<page>` (`__NEXT_DATA__` → `profile.sections[].items[].event`: the **next 30** events — `name`, `dates.event_start_date` (with offset), `status`, `price.amount` pence incl. fees), then `GET https://dice.fm/event/<id>` per event (`__NEXT_DATA__` → `initialState` (JSON string) → `event.event`: `tags_types[].value`, `about.description`, `perm_name`) | the next 30 events with type tags and descriptions; **no genre tags** |

Rules for the keys (owner decision, 2026-10-24, `docs/london.md`): a venue's
key is used **only for that venue's own events** (exactly what its public
widget shows) and the page publishing it is recorded (`key_origin`). Never
use one venue's key for another. When DICE grants Cartelita a partner key,
switch every venue to key mode. Pagination: the API's `links.next` points at
`events-api.dice.fm`, which refuses widget keys — page by `page[number]` on
the partners host instead. Islington Assembly Hall's page has an `apiKey`
too, but it's its cookie-banner key (CIVIC), not DICE's; 91 Living Room's
widget publishes only a `partnerId`.

DICE venue pages were found in DICE's own venue sitemap
(`https://dice.fm/sitemaps/venues/sitemap.xml`, 31 parts), matched by name;
the DICE venue name must match exactly (91 Living Room is "Ninety One " with a
trailing space). Events whose venue list doesn't include that exact name are
dropped (co-hosted events listed at a partner venue).

## Fields

| Field | Source |
|---|---|
| `title` | `name` |
| `start_date`/`start_time` | key: `date` (UTC) → `timezone` (Europe/London); public: `event_start_date` (offset) → London. DICE's start time is usually doors. |
| `price` | sold out → `"sold-out"`; else ticket prices in pence **incl. DICE fees** (what you pay on DICE) → `format_gbp_range` (2x rule) |
| `source_url` | `https://dice.fm/event/<hash>-<perm_name>` (key) / `https://dice.fm/event/<perm_name>` (public; perm_name already starts with the hash) |
| `external_id` | DICE event `id` |
| `description` | `raw_description` (key) / `about.description` (public) — DICE markdown |
| `image_url` | `event_images.landscape` (key) / `images.square` (public) |
| `annotations` | key mode: genre tags without prefix ("indie", "post punk") |

## Curation — DICE's own type tags

Per venue, a map from DICE **type tag** to our category (`dice_london.py`):
`music:gig` at gig venues; `music:dj` + `music:party` at clubs (Phonox,
Colour Factory, FOLD, Village Underground). Unmapped types are dropped:
`culture:comedy` (Union Chapel's comedy nights, MOTH's), quizzes/socials,
and DJ/party nights at gig venues (Oslo's Locomotive Disco, Hootananny's bass
parties, MOTH's pop parties). Cancelled events are dropped.

Key mode adds a **genre refinement** for MOTH (a pop-mapped gig venue): the
first genre tag in `GENRES` decides — rock family (`gig:rock`, `punk`,
`postpunk`, `hardcore`, `metal`, `garagerock`, `noiserock`, `alt_rock`,
`indierock`…) → rock; `gig:folk`/`folkrock`/`folkpop` → folk; otherwise pop.

## Quirks

- Public mode sees only the next 30 events: a busy venue's horizon is a few
  weeks (Phonox, The Black Heart); quiet ones months. Fine for "tonight over
  someday"; a partner key lifts it.
- Windmill Brixton sells only part of its programme on DICE (door-only shows
  aren't there) — 16 events; its own site would complete it.
- Prices include DICE's booking fee, unlike the Spektrix venues (face value).

## Ownership

These venues are owned here; keep them off other London whitelists
(jazzlondonlive lists 91 Living Room — exclude it there; Clusterflick lists
EartH's screenings — not on the film whitelist).

## Verification

Last verified **2026-10-24**, live: 599 events across the 22 venues, 100%
priced, ~100% with descriptions. Cross-check: The Lexington, Heavy Wild (EP
Launch) — 27 Oct 19:00, £11.44 — matches the event page's JSON-LD
(`startDate 2026-10-27T19:00:00+00:00`, `lowPrice 11.44`). Dropped-item
spot checks: Union Chapel's 3 comedy nights, Oslo's 10 DJ nights,
Hootananny's 8 party/DJ nights.
