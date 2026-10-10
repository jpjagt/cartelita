# jazzin.amsterdam — source map

Multi-venue source feeding every Amsterdam venue (city `amsterdam`).
jazzin.amsterdam is a set of hand-curated Amsterdam culture calendars (Next.js
on Vercel); its own pages render from the public JSON API we use.

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
| `id` | `external_id` | per occurrence, stable |
| `title` | `title` | |
| `date` (`YYYY-MM-DD`) | `start_date` | |
| `time` (`HH:MM:SS`) | `start_time` | always present |
| `site` | `source_url` | the venue's page; sometimes a generic agenda URL; stray quotes stripped (the w139 feed appends `'`); fallback `https://jazzin.amsterdam/` |
| `price` | `price` | free text: `""`/`"€"` → None; `free`/`0`/`€0` → `free`; `s.o.` → `sold-out`; amounts (`€13`, `EUR 15.00`, `€12.5–€25`, `6 / 12.5`) → `13€`, `12,50–25€` with the 2× range rule; amount-less text (`donatie`, `tips`) passes through minus a leading `€`/`EUR` (`€Sliding scale donation`; bare `EUR ` → None) |
| `venue` | `venue_slug` | via the `VENUES` alias table (case/whitespace-insensitive) |
| `address`, `source`, `calendar`, `reviewed` | — | `source` is jazzin's own scraper id |

No description, image, or genre tags. Film events never carry a price.

## Quirks

- **Duplicate listings:** occurrences repeat under several ids, within a
  calendar (Muziekgebouw: the same concert 5×) and across calendars (a
  Concertgebouw gig in jazz and classical). Merged on (venue, date, time,
  casefolded title), keeping the lowest id and the union of categories.
- **Venue categories:** `VENUES` lists, per venue, the calendars it appears
  in; each becomes a list membership whitelisted to that category (multi-
  category venues like Melkweg = jazz/pop/club split correctly). A venue
  turning up in a new calendar is logged (`venues with events in categories
  they aren't listed for`) — add the category to its row.
- **Title status markers:** `(sold out)` / `(uitverkocht)` → price
  `sold-out`, marker stripped; `[CANCELED]` (and Dutch variants) → skipped.
- **Excluded venues:** Comedytrain's Westergas halls (`Grote Zaal`, `Kleine
  Zaal`, `Comedytrain - …`; jazzin's `toomler` feed gives junk titles like
  `20:30 uur`), and venues in other cities (Leiden, Utrecht, Woerden, Laren,
  Hillegom). From the alternative calendar:
  - `Filmhuis Cavia` and `Nassaukerk` (Cavia's one-off "Cavia in Concert"
    screening there): own scraper, `filmhuis_cavia.py` (venue slug
    `filmhuis-cavia`); a second source owning that slug would collide.
  - `Bar Bario`: closed (its site announces the closure); jazzin's `barbario`
    feed re-dates its past events into 2027.
  - Not venues: `Amsterdam` (bare city, address `, Amsterdam`); the street
    corners of the weekly "Vlaggen voor Palestina" vigils (`Buikslotermeerplein`,
    `Op de brug`, `Jan van Galenstraat A10 snelweg`); `Fossil Free Culture NL`
    (an organisation, address just `Overtoom, Amsterdam`).
  No event is filtered by title.
- **Venue name spellings vary** per upstream source: `ZOJazz Stage` /
  `ZOjazz Stage` / `ZOJazzstage ` / `Concertzaal` (same building), `CvA` /
  `Amsterdam Blue Dock, CvA`, `Greene Room` with two addresses. Alternative
  calendar: `Plantage Dok` / `Dokhuis Galerie` / `Dokhuis` / `Plantage Doklaan
  8-12` (one complex; its own feed and squatradar list the same DOK Night);
  `LAG` (a group meeting at Bollox) → Infokafee Bollox; `Stichting Malak` /
  `Het Sociaal Centrum` (tenants, G.J. Scheurleerweg 212) → Het Groene Veld;
  `Het Groene Veld / ADM Noord` → Het Groene Veld (Machinegebouw)
  (Buikslotermeerdijk 95, a separate site). All mapped in `VENUES`.
- **`00:00` times** in the alternative calendar (NieuwLand's KABRA sessions,
  a W139 ADE night) are kept as midnight: jazzin's own page renders them at
  the end of the previous day, so it's the source's value, not a sentinel.
- **Whitelist:** events at venues not in `VENUES` are dropped and logged as a
  warning (`dropped events at venues not in VENUES: …`). jazzin accepts
  user-submitted gigs at one-off venues, so new names appear over time; add
  them to `VENUES` deliberately. Nearby towns (Aalsmeer, Amstelveen, Ankeveen,
  Diemen, Duivendrecht, Weesp, Zaandam) are included on purpose.
- Some addresses come as just `Amsterdam`; those were filled in by hand.

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
