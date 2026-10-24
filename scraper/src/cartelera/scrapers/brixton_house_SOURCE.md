# Brixton House — source map

Venue slug: `brixton-house` (London) — 385 Coldharbour Lane, SW9 8GL (the
former Ovalhouse). Categories `theater` and `kids` (lists `theater` and
`kids`, each whitelisted to its category).

Data: Spektrix client `ovalhouse` via `_spektrix.py` (see
`spektrix_SOURCE.md`). All seating plans belong to the Brixton House
building (client venues Theatre 1/2, Studio 4/5), so no venue split.
Show pages (`https://brixtonhouse.co.uk/shows/<slug>/`, linked from
`/whats-on/`) link each performance as **`/book-online/<numeric instance
id>`**. The module fetches the show pages itself (they also give the price,
below), takes their ids with `spk.embedded_ids` and hands them to
`spk.scrape(page_ids=…)`; the show-page price is applied in its `finish`
hook.

## Curation

Two of the box office's attributes:

- **`Season` must be an artistic season ("Season 10", "Season 9").** Dropped:
  "Creative Engagement" (the Take Part participation programme: October Half
  Term Activities, Young Associates Sharing, choir showcase), "Hires"
  (Kromanti dominoes night, Age UK comedy), "Commercial" (Pop Up & Vibes,
  "Secure My Booking").
- **`Genre`**: New Writing → theater; Youth Theatre → theater (in the
  artistic season this is a full production — Synergy Theatre Project's
  *Providers*, professionals and ex-prisoners, 17 performances; youth
  sharings sit in Creative Engagement and are already out); Family Events →
  kids (Santa's Christmas Cold, Golden Toad Theatre + Brixton Chamber
  Orchestra). Dropped genres: Comedy and Late Night Events (no comedy
  category), Live Art (CASA's *Lines of Flight*: one Spektrix event for a
  multi-arts umbrella of exhibitions, residencies, screenings, workshops and
  a closing party — not a show), Music (Kindrd Jam), Poetry, Spoken Word and
  Literature (Jawdance), Talks and Workshops, Community Projects. Touch tours
  and post-show Q&As have no genre.

## Fields beyond the helper

- **`price`: from the show page**, its "Tickets: £24 / £20 concessions" line
  → the first (full) amount, "£24". The Spektrix price lists hold the amount
  before a per-ticket charge (Standard band £21.40 for the £24 ticket, Pay
  What You Feel "£8" = 5.40), so they read £2–3 low. Events without a joined
  page keep the price-list price.
- `title`: bracketed run tags are stripped ("Providers [2027]" →
  "Providers").

## Verification

Last verified **2026-10-24**, live: 50 performances, 5 shows (4 theater, 1
kids), 50/50 priced, all linked to brixtonhouse.co.uk. Providers: 17
performances 10–20 Mar, dates and times identical to the page (Wed 10 Mar
2:00pm … Sat 20 Mar 7:00pm, incl. the 11:00 schools' matinees), "£16"
matching "Tickets: £16 / £12 concessions". Baby "£24" matches "Tickets: £24
/ £20 concessions".
Cold-start DB: same row count as the scraper output (no collapsed occurrences).
