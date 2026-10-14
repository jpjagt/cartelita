# lantarenvenster — LantarenVenster (Rotterdam)

Arthouse cinema + music venue (jazz, world, soul). WordPress + "Theater for WP"
plugin. Plain httpx works (no bot protection; robots.txt allows all).

## Data source

- **Agenda: the homepage** `https://www.lantarenvenster.nl/` →
  `.wpt_context_agenda .wp_theatre_event` (~400 elements: every screening for
  ~10 days ahead plus all announced specials/concerts up to a year ahead).
  - date: the CSS class `YYYY-MM-DD` on the element
  - times: `.wpt_production_dates_summary_times li` = ALL of that production's
    times that day (the element repeats per screening, so we group by
    (production URL, date) → one event with `start_times`)
  - title `.wp_theatre_event_title`, subtitle (appended for music only — the
    performers/support), excerpt, image, link (`/programma/<slug>/`)
  - flags (CSS classes): `film-groep` / `muziek-groep`, `premierefilm`,
    `familiefilm`, `filmspecial`, `muziek`, `muziekspecial`, `global`,
    `special`, `dans`, `boekpresentatie`, `english`; series `.wp_theatre_prod_serie`
  - sold out: `.wp_theatre_event_tickets_status_soldout`; free: tickets text "gratis entree"
- **Detail page** per production (one GET each, ~150): `.wpt_context_details`
  `.wp_theatre_prod_prices` ("€ 21 incl. € 3,00 servicekosten" → `21€`; films
  say "vanaf € 10", the student tier), `.wp_theatre_prod_languages_spoken` /
  `_subtitles` → language "Turks (Nederlands ondertiteld)" (films only).
- **House film price**: `/kaartverkoop/` "Entreeprijzen film € 13,00" → `13€`
  for films (the regular adult ticket).
- The RSS feed `/upcoming_events` and `wp-json/wp/v2/wp_theatre_prod` only have
  productions (no dates) — not used.

external_id: `<production slug>@<date>`.

## Categories (venue's own flags)

- `film-groep` → film; with `familiefilm` → **kids only**. Film concerts
  (film-groep + muziek-groep) → film.
- `muziek-groep` → jazz (the venue's music programme is jazz-led; the site has
  no finer genre than "muziek"); with `global` → folk.

## Exclusions (curation)

- `special` flag: Jazz Yoga, Dial Q film quiz, Rotterdams Open Doek (open
  screen for local makers) — side formats, not programme.
- `dans`: Salsa aan de haven (recurring salsa dance night).
- `boekpresentatie`: book launches.
- "Verwacht vanaf …" entries (announced films without screenings yet).
- Known residue: "Workshop Young Blood Brass Band" carries only
  `muziekspecial` (same as real music specials) — no structural signal, kept.

Last verified: 2026-10-14 via HTTP cross-check — the independent /muziek/
production listing (dates summary, sold-out class) vs scraper output: dates,
times, prices agree; the only /muziek/ entries absent were series index pages
(no dates) and the documented exclusions. Film "Yellow Letters" detail page:
times, language and "vanaf € 10" (→ house 13€) agree. Live run: 301 events
(386 sessions), 2026-10-14 → 2027-10-16; film 161, kids 71, jazz 68, folk 1;
time 100 %, price 300/301, language 219/301 (all films with stated languages).
