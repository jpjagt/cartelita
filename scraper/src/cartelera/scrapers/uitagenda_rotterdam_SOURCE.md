# uitagenda-rotterdam — source map

Multi-venue WHITELIST source (Rotterdam Festivals' Uitagenda,
uitagendarotterdam.nl) for Rotterdam theatre houses without a better own feed.
Client: plain httpx, honest UA `Mozilla/5.0 (compatible; Cartelita
(+https://cartelita.co))`. No bot protection.

## Calls (Umbraco JSON API: `/umbraco/api/Entity/GetProductions`)

| call | params | size | use |
|---|---|---|---|
| theater tree | `id=1083&pageSize=6000&culture=nl-NL&p=1&genre=theater&genre=cabaret&genre=dans-en-ballet&genre=jeugdtheater&genre=musical-of-show&genre=opera` | ~12 MB, ~1100 items | all items |
| dance landing | `id=17488` (page `/ontdek/dans-in-rotterdam/`) | ~1 MB, ~150 items | dance id set |
| location pages | `id=49556` (Mooi Weer), `id=49376` (Hofplein) | ~0.5 MB each | genre-less items at single-discipline houses |

Genre filter semantics (measured): repeated `genre` values are OR-ed; the bare
parent `genre=theater` only matches the "Toneel" sub-genre (626 items), so each
sub-genre of the Theater tree must be listed. A sub-genre without its parent
(`genre=dans-en-ballet`) is ignored (returns everything). The unfiltered call is
~35 MB — never used. `id=<page or location node>` scopes the result to that
landing page / location.

## Fields (per item = one production-DAY)

- `date` ISO start of the day's first session; `key` = `dd-mm-yyyy-hhmm`.
- `dates[]`: every session of the production, NO year (`dateBeautifiedShort`
  "Wo 14 okt", `timeBeautified` "19:00 - 23:00", `soldout`, `location`,
  `ticketUrl`). Same-day sessions (matched on day+month, same location) →
  `start_times`; a single session's end → `end_time`.
- title: `title` + `ageIndication` re-joined (the agenda splits "(…)" or
  "/ 8+" off the title: "Carmen" + "must die" → "Carmen (must die)",
  "Dag poes /" + "4+" → "Dag poes / 4+").
- `textShort` → description; `image` → image_url; `url` → source_url
  (the agenda production page).
- `external_id` = `{parentId}@{key}` (parentId = production node; one item per
  production-day, so unique per occurrence).
- price: NOT in the feed → None; `"sold-out"` when all the day's sessions are
  `soldout`. (Production pages sometimes show a price; not fetched — N extra
  requests.) language: None (not stated).
- 07:00 is Theater Rotterdam's "time not set" placeholder → start_time None.

## Whitelist (location id → venue)

| location (id) | venue slug |
|---|---|
| TR25 Schouwburg (49531), TR8 William Boothlaan (49401) | `theater-rotterdam` |
| Kantine Walhalla (49729), Theater Walhalla (49658), Werkplaats Walhalla (49352) | `theater-walhalla` |
| Theater Mooi Weer (49556) | `mooi-weer` |
| Jeugdtheater Hofplein (49376) | `hofplein` |

One venue per programming organisation (its halls/buildings are folded in;
the venue address is the main hall's). The plan's `kantine-walhalla-rotterdam`
became `theater-walhalla`: Kantine Walhalla is one of Theater Walhalla's three
halls, all fed from one programme/ticket shop.

Not whitelisted, with reason:
- **Maaspodium** (49504) — Maas theater en dans' own stage; owned by the
  `maas` source (richer: own genres, prices).
- **Keilepand** (49495) — not a Theater Rotterdam stage in the feed: a
  multi-tenant building whose items are food events, film-brunches and a club
  night. TR's Keilezaal does not appear separately.
- Theater Zuidplein / Luxor — owned by other batches' sources.

## Categories (agenda's own genre structure, never titles)

- Item `genres[]` only lists TOP-level genres; sub-genres are invisible. So:
  `dance` iff the item is on the agenda's own dance landing (id 17488), else
  `theater` (dance and theater are exclusive here: `dans-en-ballet` is a
  sub-genre of the Theater tree, so dance items often also carry top-level
  `theater`).
- `kids` added when the item has top-level genre `kids`, an `ageIndication`
  like `N+` with N < 12, or the venue is Jeugdtheater Hofplein (a youth theatre).

## Exclusions (curation)

- Items with top-level genre `culinair` (dinner shows, "Open Table" dinners),
  `workshop`, `evenementen` (tours, talks, markets…) or `expo`.
- Items outside the Theater genre tree (concerts, film, nightlife), incl.
  genre-LESS items at Theater Rotterdam / Walhalla (observed: a Belle &
  Sebastian concert, Left of the Dial festival, a pub quiz, some cabaret/
  performance items the agenda left untagged — dropped rather than guessed).
- Genre-less items at the single-discipline houses Mooi Weer and Hofplein ARE
  kept as theater (e.g. Mooi Weer's "Toneelstuk Oedipus").
- Duplicates: two feeders sometimes enter one show twice (Walhalla's own feed
  + its ticket shop). Same location + same start + same first title word + ≥50%
  title-word overlap → keep the first ("Christmas Inc, een…" / "Christmas Inc -
  een…"; TR's "FUTURE VOICES" double bill listed whole and per part).

## Verification

Last verified: 2026-10-14 via HTTP cross-check. Scraper run live (522 events:
TR 198, Walhalla 146, Hofplein 107, Mooi Weer 71; 2026-10-14 → 2027-06-27;
time 98%). Independently fetched the per-LOCATION API pages (a different call)
for Mooi Weer, TR25, Kantine Walhalla, Hofplein and matched the first 7 items
each by date/time/title: all present with matching title/time except the
genre-less TR items excluded by design ("Welcome to our Guesthouse").
Production pages (Pietje Bell, De Vader) parsed for their session tables:
dates and times match the scraper's occurrences.
