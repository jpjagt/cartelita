# SAT! Sant Andreu Teatre — source map

Venue: SAT! Sant Andreu Teatre (Sant Andreu, Barcelona). Family/kids theatre,
contemporary dance, circus, music. Site is a Koobin-backed CMS (Catalan).

## List URL (show discovery)
- `https://www.sat-teatre.cat/ca/programacio.html` — renders ALL current/future
  shows server-side (no date filter applied = "Totes les dates"; no pagination).
  Each show is a `.row[data-open-espectacle]` card:
  - detail URL: `data-open-espectacle` attribute (e.g. `.../ca/p/c/684-girafa.html`)
  - title: `.titol`
  - company/subtitle: `.subtitol`
  - genre tags: `.cf.op-multiple .v` (e.g. "Dansa", "Familiar", "Circ", "Titelles",
    "Teatre", "Teatre musical", "Festival Grec"). These are the CATEGORY discriminator.
  - The card shows only a date RANGE (`.data-inici` / `.data-fi`), NOT per-session.

## Detail page (per-session dates — one ScrapedEvent per session)
- The "Calendari i Sessions" rows view: `#funcions .funcio` — one element per session.
  - session id: class `funcio-<id>` (e.g. `funcio-4820`) -> used in external_id
  - date+time: parsed from the session's buy link
    `a.comprar[href*=koobin]` -> `.../girafa-20260709-1830` (local `YYYYMMDD-HHMM`).
    Fallback: the Google-calendar link `a[href*=google.com]` `dates=YYYYMMDDTHHMMSS`
    (UTC; would need +1/+2h tz shift — buy link is preferred, already local).
  - price: `.preu .valor` (e.g. "12 €"). "Des de" prefix lives in a separate `.desde`.
  - genre tags also present on detail page (`.custom-fields .v`) but list-page cf is
    cleaner (detail page interleaves "Sense text" / "A partir de N anys" age labels).
- image: `meta[property="og:image"]`.

## Category-mapping rule (genre tag -> slug; a show may emit several slugs)
- dance:   Dansa, Contemporània, Urbana, Moviment
- kids:    Familiar  (SAT is primarily a family/kids venue)
- theater: Teatre, Circ, Titelles, Teatre visual, Clown, Teatre musical,
           Multidisciplinar, Tradicional
- pop:     Música
- classical: Clàssica
- flamenco:  Flamenco
- IGNORED (not a genre): "Festival Grec" (festival label) -> annotation.
- Fallback if no tag maps: theater.

## external_id
Per OCCURRENCE: `f"sat-{funcio_id}"` (each session row has a globally-unique funcio
id). Falls back to `f"{show_slug}@{date}T{HHMM}"` if no funcio id is found.

## Quirks
- Year is NOT in the visible `.dia`/`.mes`; take it from the buy-link date string.
- "12 €" uses a non-breaking space; normalize.
- All three current shows are Grec-festival family shows (June 2026 recon window).

Verified: 2026-06-09

## Live verification (2026-06-09)
Scraper output cross-checked field-by-field against the live DOM:
- 7 events from 3 shows; price 7/7, start_time 7/7; all external_ids unique.
- PYYKKI 3 sessions (02 jul 18:30 / 03 jul 16:00 / 03 jul 19:00), Girafa 09+10 jul
  18:30, La Júlia 16+17 jul 18:30 — all 12€. Matches the funcio ids (4820-4826),
  buy-link dates and `.preu .valor` read off the live pages. AGREES.
