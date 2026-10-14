# doelen — De Doelen + Theater Zuidplein (Rotterdam)

One source, two venues: both sites run CultureSuite "Peppered" with the same
agenda template. Code: `doelen.py` (`SITES` holds the per-site config).

| venue | slug | list URL |
|---|---|---|
| De Doelen | `de-doelen` | https://www.dedoelen.nl/nl/agenda (`?p54_page=N`, ~4 pages × 50 productions) |
| Theater Zuidplein | `theater-zuidplein` | https://www.theaterzuidplein.nl/agenda (`?p54_page=N`, ~18 pages × 9) |

## Client / queue gate

Both sites sit behind a CultureSuite queue ("csq"). When it's active, a plain
GET answers `307 → /csq/` (body "redirecting to queue"); a JS challenge sets a
`csq_token` cookie (per domain). The scraper tries plain httpx first; on the
gate it does ONE headless pass with `cartelera.scrapers.browser.browser_page(
<agenda>, wait_for="li.eventCard")`, then fetches all pages over httpx with the
returned cookies + User-Agent (the token works with plain HTTP). The gate was
active intermittently during recon (2026-10-14); the browser pass takes ~10-60 s.

## Fields (list page only; no detail pages)

- card: `li.eventCard[data-entry-id]` (one per production)
- occurrences: `li.subshow` rows when present (multi-date productions and
  same-day double shows), else the card itself
- start: `[data-event-start]` ("2026-10-14 20:15:00") on the order/wishlist
  button; fallback text `.date .start` ("wo 14 okt 26" Doelen, "wo 14 okt"
  Zuidplein — year inferred from the weekday) + time (`dl.intermission` strong
  "start" dd, or `.time .start`)
- title `.title` (+ ` — <subtitle>` when the subtitle is ≤ 40 chars, i.e. a
  performer name); description = subtitle/`.tagline`; link `a.desc`; image `.thumb img`
- hall: `.venue` → annotation
- price: popover table `.item-prices tr` (`.pricetype` + `td.price`), skipping
  youth/CJP/early-bird/supporter/dinner tiers; `status-uitverkocht`, all rows
  `is-soldout`, or an "uitverkocht |" title prefix → `sold-out`;
  `status-vrij_entree` → `free`. Range only when hi ≥ 2× lo.
- language: genre "nederlandstalig" → `NL`; "Mime (woordloos)" → `non-verbal`
- external_id: `<data-entry-id>@<date>T<HHMM>`
- annotations: the genre labels that aren't category discriminators, minus
  marketing labels (jongerentarief, seizoen 26/27, jubileum…, gratis), + hall

## Categories (the venues' own genre labels, `.genres__link`)

De Doelen: klassiek → classical, jazz → jazz, pop → pop, global → folk
(world music: fado, Anatolian, Kurdish, Iranian…). Multiple labels → multiple
categories (Codarts "Jazz & Global Sessions" = jazz + folk).

Theater Zuidplein: Toneel/Muziektheater/Comedy-Cabaret/Stand up/Theater/
Bewegingstheater/Mime/Poppentheater/Musical/Opera/Storytelling/Verteltheater/
Spoken Word/Crossover → theater; Dans → dance; Popmuziek/Muziek/Hiphop → pop;
Wereldmuziek → folk; **Jeugd & Familie → kids only** (exclusive).

## Exclusions (curation; all by the venue's own structural signals)

- De Doelen **"talk"** label: book presentations and live podcasts (Hagelslag,
  Aboutaleb, Schimmelpenninck, Ottolenghi) — not concerts.
- De Doelen **"live in concert"-only** productions (no other music label):
  touring film/game-score shows (Harry Potter, Witcher, Demon Slayer, Hans
  Zimmer tribute…) — ~14 productions of mainstream touring fare.
- De Doelen **no genre label**: hires/test entries (Rotterdam Coffee Fest,
  Ballet of Lights, "TEST").
- Zuidplein **"Overig"**: Sip & Paint workshops, open rehearsals, a Miss
  Curaçao pageant, long-running community series.
- Zuidplein **"Gastprogramma"**: guest hires (Outdoor Film Tour, salsa
  festival, third-party shows).
- Zuidplein "Film" (only ever seen with Gastprogramma) maps to nothing.
- Zuidplein **no genre label**: a handful of untagged co-productions — no
  discriminator to categorize them by.
- Cancelled: title prefix "geannuleerd |"/"afgelast |", `status-geannuleerd`,
  hall "Geannuleerd/Vervallen"; Zuidplein `status-test` (internal entries).
- Occurrences before today ("Geweest" subshow rows).

## Quirks

- Resident orchestras' concerts (Rotterdams Philharmonisch, Sinfonia
  Rotterdam) are `status-externe_verkoop`: tickets via the orchestra's site, NO
  price on the Doelen list → price None (~1/3 of Doelen events). They ARE
  Doelen programme and are kept.
- Title status prefixes "uitverkocht | ", "verplaatst | " are stripped
  (verplaatst → annotation).

Last verified: 2026-10-14 via HTTP cross-check (independent parse of
`data-event-start`/`data-production-title`/`.pricePopoverBtn` on fresh pages
Doelen p2 + Zuidplein p3 vs scraper output: dates, times, titles, halls,
prices agree; differences were exactly the documented exclusions and the
2× range rule). Live run: Doelen 170 occurrences (2026-10-15 → 2027-06-19),
Zuidplein 177 (2026-10-14 → 2027-07-09); time 100 %, price 66 % / 95 %.
