# jazzin.amsterdam — source map

Multi-venue source feeding every Amsterdam venue (city `amsterdam`, list `jazz`).
jazzin.amsterdam is a hand-curated Amsterdam jazz calendar (Next.js on Vercel);
its own pages render from the public JSON API we use.

- **API:** `GET https://jazzin.amsterdam/api?calendar=jazzAmsterdam&archive=false&offset=N`
  → JSON array of events, at most 600 per call. `page` is ignored; page with
  `offset` (0, 600, …) until a short page. ~640 upcoming events (Oct 2026), a
  year ahead. Calling the bare `/api` returns usage + the maintainer's contact
  (jazzinmokum@gmail.com) asking to be told if you use it.
- **Other calendars** on the same API: `classicalAmsterdam`, `theaterAmsterdam`,
  `alternativeAmsterdam`, `popAmsterdam`, `clubAmsterdam`, `filmAmsterdam`
  (arthouse), `movieAmsterdam` (Pathé). Not used yet.

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

No description, image, or genre tags. Category is always `jazz` (the calendar
is the discriminator).

## Quirks

- **Duplicate listings:** some sources repeat an occurrence under several ids
  (Muziekgebouw: the same concert 5×). De-duplicated on
  (venue, date, time, casefolded title), keeping the lowest id.
- **Venue name spellings vary** per upstream source: `ZOJazz Stage` /
  `ZOjazz Stage` / `ZOJazzstage ` / `Concertzaal` (same building), `CvA` /
  `Amsterdam Blue Dock, CvA`, `Greene Room` with two addresses. All mapped in
  `VENUES`.
- **Whitelist:** events at venues not in `VENUES` are dropped and logged as a
  warning (`dropped events at venues not in VENUES: …`). jazzin accepts
  user-submitted gigs at one-off venues, so new names appear over time; add
  them to `VENUES` deliberately. Out-of-town venues (Aalsmeer, Ankeveen,
  Diemen, Weesp) are included on purpose.
- Some addresses come as just `Amsterdam`; those were filled in by hand.

Last verified: 2026-10-10 via HTTP cross-check. The first 25 events on the
rendered homepage (`https://jazzin.amsterdam/`, parsed independently) all
matched the scraper on title, time, venue and price. Live run: 640 raw → 557
events, 0 unknown venues, 100% times, 71% prices (the rest are blank upstream).
