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
  cinemas) → film. ~5,300 raw events (Oct 2026), up to a year+ ahead (film:
  ~5 months).
- **Not used:** `alternativeAmsterdam` (the site's "independent": a grab-bag of
  yoga, lunches, workshops and gigs) and `movieAmsterdam` (Pathé multiplexes,
  ~200 screenings/day, only 3 days ahead).

## Field map (event object → ScrapedEvent)

| API field | ScrapedEvent | notes |
|---|---|---|
| `id` | `external_id` | per occurrence, stable |
| `title` | `title` | |
| `date` (`YYYY-MM-DD`) | `start_date` | |
| `time` (`HH:MM:SS`) | `start_time` | always present |
| `site` | `source_url` | the venue's page; sometimes a generic agenda URL; fallback `https://jazzin.amsterdam/` |
| `price` | `price` | free text: `""`/`"€"` → None; `free`/`0`/`€0` → `free`; `s.o.` → `sold-out`; amounts (`€13`, `EUR 15.00`, `€12.5–€25`, `6 / 12.5`) → `13€`, `12,50–25€` with the 2× range rule; amount-less text (`donatie`) passes through |
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
  Hillegom).
- **Venue name spellings vary** per upstream source: `ZOJazz Stage` /
  `ZOjazz Stage` / `ZOJazzstage ` / `Concertzaal` (same building), `CvA` /
  `Amsterdam Blue Dock, CvA`, `Greene Room` with two addresses. All mapped in
  `VENUES`.
- **Whitelist:** events at venues not in `VENUES` are dropped and logged as a
  warning (`dropped events at venues not in VENUES: …`). jazzin accepts
  user-submitted gigs at one-off venues, so new names appear over time; add
  them to `VENUES` deliberately. Nearby towns (Aalsmeer, Amstelveen, Ankeveen,
  Diemen, Duivendrecht, Weesp, Zaandam) are included on purpose.
- Some addresses come as just `Amsterdam`; those were filled in by hand.

Last verified: 2026-10-10 via HTTP cross-check. The first 15 rows of each
calendar's rendered page (`https://jazzin.amsterdam/<calendar>`, parsed
independently) vs the scraper: jazz, classical, pop 15/15; theater 13/15 and
club 14/15, the misses being the excluded Comedytrain rows and a
`[CANCELED]` gig; film 11/15, the misses being screenings that had just
started (the cached page still showed them, the API had dropped them).
Jazz homepage price check: 25/25. Live run: 5,336 raw → 4,687 events
(jazz 557, classical 993, theater 1,324, pop 395, club 437, film 1,109), 158
venues, 100% times.
