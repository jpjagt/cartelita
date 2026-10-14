# jazzin.amsterdam — source map

Multi-venue source feeding every Amsterdam venue (city `amsterdam`).
jazzin.amsterdam is a set of hand-curated Amsterdam culture calendars (Next.js
on Vercel); its own pages render from the public JSON API we use.

**Opt-out source (decided 2026-10-13).** Unlike the other aggregators (whose
venue list is an editorial whitelist — multi-city design §1), every venue
jazzin names becomes a venue automatically; code holds only the exceptions.
Rationale: jazzin is itself hand-curated, it accepts user-submitted gigs at
one-off venues, and the whitelist was silently dropping real venues (Frascati,
120 events; Felix Meritis; ITA) until someone noticed the log line. The
editorial check moves from "before anything shows" to a review issue after
the fact. Exact name matching only (`_venue_key`: case/whitespace), no fuzzy
matching — spelling variants are merged by hand via aliases.

- **API:** `GET https://jazzin.amsterdam/api?calendar=<id>&archive=false&offset=N`
  → JSON array of upcoming events (already-started ones drop out), at most 600
  per call. `page` is ignored; page with `offset` (0, 600, …) until a short
  page. Calling the bare `/api` returns usage + the maintainer's contact
  (jazzinmokum@gmail.com) asking to be told if you use it.
- **Calendars → category** (the calendar is the discriminator): `jazzAmsterdam`
  → jazz, `classicalAmsterdam` → classical, `theaterAmsterdam` → theater,
  `popAmsterdam` → pop, `clubAmsterdam` → club, `filmAmsterdam` (arthouse
  cinemas) → film, `alternativeAmsterdam` (the site's "independent" tab,
  `https://jazzin.amsterdam/independent`: squats and DIY spaces — OT301,
  NieuwLand, OCCII, Vrankrijk, Tolhuistuin, De Nieuwe Anita, Volkshotel… —
  gigs, vokus, workshops, assemblies, yoga; mostly via jazzin's `squatradar`
  feed of radar.squat.net) → alternative. ~6,200 raw events (Oct 2026), up to
  a year+ ahead (film: ~5 months; alternative: ~3 months).
- **Not used:** `movieAmsterdam` (Pathé multiplexes, ~200 screenings/day,
  only 3 days ahead).

## Field map (event object → ScrapedEvent)

| API field | ScrapedEvent | notes |
|---|---|---|
| `id` | — | **not stable**: the maintainer re-scrapes everything nightly and ids change; used only to order duplicates |
| (`date`, `time`, `title`) | `external_id` | content-derived: `sha1("YYYY-MM-DDTHHMM\|<whitespace-collapsed casefolded title>")[:16]` (`none` for a missing time), title after status-marker stripping; unique per venue per batch via the occurrence merge (`occurrence_key`) |
| `title` | `title` | |
| `date` (`YYYY-MM-DD`) | `start_date` | |
| `time` (`HH:MM:SS`) | `start_time` | always present |
| `site` | `source_url` | the venue's page; sometimes a generic agenda URL; stray quotes stripped (the w139 feed appends `'`); fallback `https://jazzin.amsterdam/` |
| `price` | `price` | free text: `""`/`"€"` → None; `free`/`0`/`€0` → `free`; `s.o.` → `sold-out`; amounts (`€13`, `EUR 15.00`, `€12.5–€25`, `6 / 12.5`) → `13€`, `12,50–25€` with the 2× range rule; amount-less text (`donatie`, `tips`) passes through minus a leading `€`/`EUR` (`€Sliding scale donation`; bare `EUR ` → None) |
| `venue` | `venue_slug` | `VENUES` alias match (case/whitespace-insensitive) → that override's slug; else, unless `DENIED`, `slugify(name)` → a discovered venue |
| `venue`, `address` | discovered venue | name = the most common spelling, address = the most common one (None if just `Amsterdam`), categories = the calendars its events are in |
| `source` | — | jazzin's own scraper id; feeds in `DENIED_FEEDS` (`toomler`) are dropped whole |
| `calendar`, `reviewed` | — | |

No description, image, or genre tags. Film events never carry a price.

## Quirks

- **Duplicate listings:** occurrences repeat under several ids, within a
  calendar (Muziekgebouw: the same concert 5×) and across calendars (a
  Concertgebouw gig in jazz and classical). Merged on (venue, content key) —
  i.e. venue, date, time, normalized title — keeping the lowest id's fields
  and the union of categories.
- **Key change (2026-10-12):** external_id switched from jazzin's numeric `id`
  to the content key. Rows still on a numeric id are legacy; after deploy,
  `cartelera health rekey jazzin-amsterdam --apply` hides the upcoming ones
  (see `docs/deploy.md` § 6). A retitled event now becomes a new row and the
  old one is hidden after 3 healthy runs.
- **Venue categories:** each category a venue has becomes a list membership
  whitelisted to that category (multi-category venues like Melkweg =
  jazz/pop/club split correctly). jazzin's calendars decide categories for
  every venue (decided 2026-10-14): override venues' `VENUES` categories are
  the seeded minimum, and the source sets `extends_venue_categories`, so when
  an override venue appears in a new calendar the run adds that category + a
  whitelisted membership in the DB before writing its events (`run.
  _extend_categories`, `seed.extend_venue_categories`); `seed` keeps those DB
  additions. Each addition is printed by `cartelera run`, recorded in
  `scrape_run.metrics.new_categories` and posted to the venue-review issue
  below — mirror it in the `VENUES` row when convenient. Discovered venues
  gain categories the same way (not reported). Nothing is ever removed
  automatically; a wrong category is removed by hand (venue_category +
  list_venue rows) after fixing its cause in code.
- **Title status markers:** `(sold out)` / `(uitverkocht)` → price
  `sold-out`, marker stripped; `[CANCELED]` (and Dutch variants) → skipped.
- **Denylist (`DENIED`, `DENIED_FEEDS`)** — names that never become venues,
  each with its reason in code:
  - `toomler` feed (Comedytrain's Westergas halls: `Grote Zaal`, `Kleine
    Zaal`, `Comedytrain - Westergas - …`): junk titles like `20:30 uur`. The
    bare hall names are also denied by name.
  - Outside the Amsterdam area (the `cva` feed lists the Conservatorium's
    concerts elsewhere): `Stadsgehoorzaal Leiden`, `TivoliVredenburg`
    (Utrecht), `Theater Het Klooster Woerden`, `Papagenohuis` (Laren), `De
    Kulturele Raad` (Hillegom). Nearby towns (Aalsmeer, Amstelveen, Ankeveen,
    Diemen, Duivendrecht, Weesp, Zaandam) are in, as overrides.
  - Owned by a dedicated scraper: `Filmhuis Cavia` and `Nassaukerk` (Cavia's
    one-off "Cavia in Concert" screening there) — `filmhuis_cavia.py`, venue
    `filmhuis-cavia`.
  - Closed: `Bar Bario` (its `barbario` feed re-dates past events into 2027).
  - Not venues: `Amsterdam` (bare city, address `, Amsterdam`); the street
    corners of the weekly "Vlaggen voor Palestina" vigils (`Buikslotermeerplein`,
    `Op de brug`, `Jan van Galenstraat A10 snelweg`); `Fossil Free Culture NL`
    (an organisation, address just `Overtoom, Amsterdam`).
  Denied names are logged as one count (names at debug level). No event is
  filtered by title.
- **Venue name spellings vary** per upstream source: `ZOJazz Stage` /
  `ZOjazz Stage` / `ZOJazzstage ` / `Concertzaal` (same building), `CvA` /
  `Amsterdam Blue Dock, CvA`, `Greene Room` with two addresses. Alternative
  calendar: `Plantage Dok` / `Dokhuis Galerie` / `Dokhuis` / `Plantage Doklaan
  8-12` (one complex; its own feed and squatradar list the same DOK Night);
  `LAG` (a group meeting at Bollox) → Infokafee Bollox; `Stichting Malak` /
  `Het Sociaal Centrum` (tenants, G.J. Scheurleerweg 212) → Het Groene Veld;
  `Het Groene Veld / ADM Noord` → Het Groene Veld (Machinegebouw)
  (Buikslotermeerdijk 95, a separate site); `Roode Bioscoop` → De Roode
  Bioscoop; `Gelvinck Pianola Museum` → Pianola Museum; `Ensemblezaal, CvA` →
  Conservatorium; `Het Verbond - Café` (Frascati's feed) → Het Verbond. All
  mapped in `VENUES`.
- **`00:00` times** in the alternative calendar (NieuwLand's KABRA sessions,
  a W139 ADE night) are kept as midnight: jazzin's own page renders them at
  the end of the previous day, so it's the source's value, not a sentinel.
- **Discovered venues (opt-out).** A name in no `VENUES` alias and not
  denied becomes a venue: slug `slugify(name)` (ascii, lowercase, hyphens,
  quotes dropped), city `amsterdam`, `venue.discovered_by =
  'jazzin-amsterdam'`. `cartelera run` creates it in the run's transaction
  (`cartelera.discovery`, `seed.upsert_discovered_venue`); it persists like
  any venue and counts as one of this source's venues for health metrics,
  hiding and `health ack`. `seed` only seeds the overrides. A discovered slug
  that a code-defined venue of any source, or a DB venue this source didn't
  create, already has is refused: its events are skipped with a warning (and
  `scrape_run.metrics.refused_venues`) — deny or merge that name.
- **Review loop.** Venues created for the first time (and categories added
  to override venues, see above) are printed by `cartelera
  run`, recorded in `scrape_run.metrics.new_venues`, and posted to one rolling
  GitHub issue, `jazzin-amsterdam: venues to review` (label
  `venue-review`; later batches are comments; once closed, the next batch
  opens a new one; without a token it's only logged). To review:
  - **merge** a spelling variant: add the name to the right `VENUES` row's
    aliases (or add a row to override name/address/categories);
  - **deny**: add the name with a reason to `DENIED`.
  The auto-created venue then gets no new events and its upcoming ones are
  hidden after 3 healthy runs (a discovered venue absent from a run is not
  health-evaluated on its own, so this doesn't flag the source); its row
  stays — `DELETE FROM venue WHERE slug = '…'` removes it (cascades).
  `cartelera dry-run jazzin_amsterdam` lists what a run would discover.
- Some addresses come as just `Amsterdam`; those were filled in by hand.
- **Venue health.** jazzin aggregates other people's scrapers, so single
  venues break upstream (2026-10-12: De FilmHallen and The Movies went to 0
  events in jazzin's film feed). Such a venue is degraded on its own — the
  source stays healthy, the venue's events are kept and not hidden — and
  after 7 consecutive degraded runs it is listed on the same rolling review
  issue (`jazzin-amsterdam: venues to review`). Decide per venue: wait, deny /
  merge it, or `cartelera health ack jazzin-amsterdam <slug>` to accept its new
  state. `cartelera health jazzin-amsterdam` lists the degraded venues.

Opt-out switch (2026-10-13), live feed: 6,537 raw → 6,106 events; 10 venues
discovered (Frascati 120 events, Theater van Deyssel 8, ITA | Internationaal
Theater 8, Felix Meritis 4, Manhattan Lounge Bar 4, and one-off gigs at Café de
Muurbloem, De Groene Olifant, Teatro Munganga, The Brokers Bar (Beurs van
Berlage), Buurthuis De Archipel) — all real Amsterdam venues, none denied;
`Roode Bioscoop`, `Gelvinck Pianola Museum`, `Ensemblezaal, CvA` and `Het
Verbond (- Café)` were made aliases/overrides instead.

Last verified: 2026-10-10 via HTTP cross-check. Alternative: the first 15
rows of `https://jazzin.amsterdam/independent` (schema.org `Event` rows,
parsed independently with BeautifulSoup) vs the scraper: 13/15 matched on
date/time/title/venue/price/URL, the misses being the excluded `Amsterdam`
and `Buikslotermeerplein` rows. Live run: 933 raw → 863 alternative events
across 42 venues (31 new; 10 existing venues gained the category), price on
14% (the squatradar feed carries none), 100% times. Whole source: 6,223 raw →
5,445 events (jazz 557, classical 993, theater 1,324, pop 395, club 437, film
1,063, alternative 863), 190 venues. Earlier (other calendars): the first 15 rows of each
calendar's rendered page (`https://jazzin.amsterdam/<calendar>`, parsed
independently) vs the scraper: jazz, classical, pop 15/15; theater 13/15 and
club 14/15, the misses being the excluded Comedytrain rows and a
`[CANCELED]` gig; film 11/15, the misses being screenings that had just
started (the cached page still showed them, the API had dropped them).
Jazz homepage price check: 25/25. Live run: 5,336 raw → 4,687 events
(jazz 557, classical 993, theater 1,324, pop 395, club 437, film 1,109), 158
venues, 100% times.
