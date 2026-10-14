# Rotterdam + Utrecht — build plan and venue ownership

Date: 2026-10-14. Based on the research report (aggregators, venue inventory,
risks). This file is the shared contract for the parallel scraper batches.

## Rules (decided with the owner)

- **Curation and quality over exhaustiveness.** Include a venue only if a
  culturally engaged local would want it on the agenda. Within a venue, use the
  source's own structural signals (categories, genres, series, sections) to
  leave out non-programme items: rentals, private events, tours, workshops,
  markets, church services, generic recurring nights. Never filter by guessing
  from title keywords. Record every exclusion and its reason in SOURCE.md.

- **One owning source per venue.** Miss-counting/health are per venue, so a
  second source feeding a venue would get the first source's events hidden.
  Aggregators (Cineville, jazz010, the uit-agendas) therefore run as
  **whitelists** (opt-in, like tomsarkgh — NOT opt-out like jazzin) and must
  not list venues owned by another source in the table below.
- **Venue slugs are global across cities.** Before adding a slug, check it
  against every registered source (`load_all()`); on a clash, suffix the city
  (`walhalla` exists in Amsterdam → `kantine-walhalla-rotterdam`).
- **No Stager** (`*.stager.co` disallows bots in robots.txt). Use venues' own
  sites; a missing price/time is acceptable.
- **Headless Chromium is allowed in production** for sites behind a queue gate
  or bot check (De Doelen/Zuidplein cookie, TivoliVredenburg) — via the shared
  browser helper added in batch 0, never ad hoc.
- Identify honestly: a stable User-Agent containing `Cartelita
  (+https://cartelita.july.dev)` (plus a browser token where a site needs it).
- Follow `.claude/skills/writing-a-scraper` (incl. `scraper/tools/recon.py`,
  `curl_cffi` for bot-protected sites) and `AGENTS.md`.
- Cities: `rotterdam` (nl/en, default nl, default list `jazz`), `utrecht`
  (nl/en, default nl, default list `pop`), timezone Europe/Amsterdam.

## Venue ownership

Slugs are proposals; the owning batch verifies uniqueness and may adjust (then
updates this table in its commit).

### Rotterdam

| Venue | Slug | Categories | Owner (source) | Batch |
|---|---|---|---|---|
| KINO | kino-rotterdam | film | cineville | 1 |
| Cinerama | cinerama | film | cineville | 1 |
| Wenneker (Schiedam) | wenneker | film | cineville | 1 |
| LantarenVenster | lantarenvenster | film, jazz | lantarenvenster | 4 |
| WORM | worm | alternative, film | worm | 3 |
| Dizzy, Vrijmoed, Fruitvis, Grounds, Heerenhuys, other jazz010 venues not owned below | (per venue) | jazz | jazz010 | 2 |
| BIRD | bird | jazz, club | bird | 3 |
| Rotown | rotown | pop | rotown | 3 |
| Baroeg | baroeg | alternative | baroeg | 3 |
| Annabel | annabel | pop, club | annabel | 3 |
| Toffler | toffler | club | toffler | 3 |
| Maassilo | maassilo | club, pop | maassilo | 3 |
| Roodkapje | roodkapje | alternative | roodkapje | 3 |
| Poortgebouw | poortgebouw | alternative | poortgebouw | 3 |
| De Doelen | de-doelen | classical, jazz, pop | doelen (Peppered) | 4 |
| Theater Zuidplein | theater-zuidplein | theater, pop | doelen (same platform) | 4 |
| Laurenskerk | laurenskerk | classical | laurenskerk | 4 |
| Luxor (optional) | luxor | theater, pop | luxor | 4 |
| Theater Rotterdam (TR25 Schouwburg + TR8 William Boothlaan; Keilepand is not TR in the feed) | theater-rotterdam | theater, dance, kids | uitagenda-rotterdam | 5 |
| Theater Walhalla (Kantine Walhalla, Theater Walhalla, Werkplaats Walhalla — one programme) | theater-walhalla | theater, dance, kids | uitagenda-rotterdam | 5 |
| Theater Mooi Weer | mooi-weer | theater | uitagenda-rotterdam | 5 |
| Jeugdtheater Hofplein | hofplein | theater, kids | uitagenda-rotterdam | 5 |
| Maaspodium (= Maas theater en dans' own stage; one venue, not two) | maaspodium | theater, dance, kids | maas | 5 |
| ~~Dansateliers~~ — not built: a production house whose agenda is its makers' touring dates; its Rotterdam shows are at TR/Zuidplein (owned above), and at its own studio only ~2 performances/season amid talks/funding sessions with no structural signal to tell them apart | — | — | — | 5 |

### Utrecht

| Venue | Slug | Categories | Owner (source) | Batch |
|---|---|---|---|---|
| Louis Hartlooper Complex | louis-hartlooper | film | cineville | 1 |
| Springhaver | springhaver | film | cineville | 1 |
| Slachtstraat Filmtheater | slachtstraat | film | cineville | 1 |
| De Sien | de-sien | film | cineville | 1 |
| De Helling | de-helling | pop, club | de-helling | 6 |
| EKKO | ekko | pop, club | ekko | 6 |
| dB's | dbs | pop, alternative | dbs | 6 |
| BASIS | basis-utrecht | club | basis-utrecht | 6 |
| ACU | acu | alternative, club, film (no pop: its own labels have no pop programme) | acu | 6 |
| KABUL à GoGo | kabul-a-gogo | club, alternative | kabul-a-gogo | 6 |
| ~~Moira~~ — not built: a squat-basement community venue; its agenda is a weekly open mic plus occasional improv, talks and workshops (3 upcoming items, no concerts) — too thin/low-signal for a curated agenda | — | — | — | 6 |
| Stadsschouwburg Utrecht | stadsschouwburg-utrecht | theater, dance | cre8ion (shared parser) | 7 |
| Theater Kikker | theater-kikker | theater, dance | cre8ion | 7 |
| Podium Hoge Woerd | podium-hoge-woerd | theater, dance | cre8ion | 7 |
| Theater Utrecht | theater-utrecht | theater, dance | theater-utrecht | 7 |
| TivoliVredenburg | tivolivredenburg | pop, jazz, classical, club | tivolivredenburg (fallback: uitagenda-utrecht whitelisted to it) | 8 |
| UJazz (optional) | ujazz | jazz | ujazz | 8 |
| Festival Oude Muziek (optional) | festival-oude-muziek | classical | oude-muziek | 8 |
| Domkerk / Pieterskerk (optional) | domkerk, pieterskerk | classical | per venue | 8 |

## Batches

0. Cities + shared browser helper + this doc's rules in AGENTS.md (alone, first).
1. `cineville` — both cities' arthouse cinemas (Cineville public API).
2. `jazz010` — Rotterdam jazz agenda (whitelist; price from detail pages).
3. Rotterdam pop/club/alternative.
4. Rotterdam institutions (LantarenVenster, Doelen + Zuidplein, Laurenskerk, Luxor).
5. Rotterdam theater/dance (`uitagenda-rotterdam` whitelist + Maas + Dansateliers).
6. Utrecht pop/club/alternative.
7. Utrecht theater (cre8ion parser ×3 + Theater Utrecht).
8. TivoliVredenburg (+ optional classical/jazz venues).
