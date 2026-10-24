# Jermyn Street Theatre — source map

Venue slug: `jermyn-street-theatre` (London) — 16b Jermyn Street, St
James's SW1Y 6ST. Category `theater` (list `theater`).

Data: Ticketsolve feed
`https://jermynstreettheatre.ticketsolve.com/shows.xml` via
`_ticketsolve.py` (see `ticketsolve_SOURCE.md`).

## Curation

No `event_category` in the feed; every show at feed venue "Jermyn Street
Theatre" → theater. Checked 2026-10-25: 6 shows / 79 performances, all
performances in the one auditorium — the main-house runs (Ghosts, It's A
Wonderful Life!) and one-off Sunday shows (Cult Figure: Kenneth Williams,
One Man Poe, ORWELL - The Road to 1984, It's All Greek). No vouchers,
memberships or workshops.

## Fields

As the helper: "Full Price £40 / Concession £35" → "£40"; sold-out
performances (the feed omits their prices) → "sold-out". Annotations from
`event_attribute`: "relaxed show", "captioned show", "relaxed
performance", "captioned performance".

## Verification

Last verified **2026-10-25** via HTTP cross-check with
jermynstreettheatre.co.uk/show/ghosts/: "8 October - 14 November 2026,
Monday to Saturday 7.30pm, Tuesday, Saturday 3.00pm … Tickets £40 (£35
conc) … Relaxed performances: Thursday 29 October 7.30pm, Tuesday 10
November 3.00pm" → scraper Ghosts 26 Oct 19:30 "£40", 27 Oct 15:00
sold-out, 29 Oct 19:30 "£40" ["relaxed show"]. 77 upcoming performances,
100% priced (incl. sold-out). Cold-start DB: 77 rows.
