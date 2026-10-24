# Camden People's Theatre — source map

Venue slug: `camden-peoples-theatre` (London) — 58-60 Hampstead Road, Euston
NW1 2PY. Fringe, devised, live art and work-in-progress → `theater` (list
`theater`).

Data: Spektrix client `camdenpeoplestheatre` (custom domain
`tickets.cptheatre.co.uk`). Built from the `_spektrix.py` steps (see
`spektrix_SOURCE.md`), run by the module itself because of one helper gap:
CPT's show pages link performances as **`/tickets/<numeric instance id>`**
(`location.href='https://cptheatre.co.uk/tickets/351844'`), a form
`_spektrix._SITE_IDS` doesn't know. The module collects those ids from the
show pages linked on `https://cptheatre.co.uk/Whats-On`
(`…/whatson/<Slug>`), then uses `site_urls`, `fetch_plan_venues`, `select`,
`fetch_prices`, `build` as `_spektrix.scrape` does. If the helper learns the
`/tickets/` pattern, this collapses to a plain
`spk.scrape(CLIENT, categorize, site=SITE, venue=venue, plan_venues=True)`.

## Curation

- No artform/type attribute: `FinancialArrangement` (Guarantee / Box office
  split / External hire / Fee / Other) and `FestivalOrStrand` (Autumn 2026,
  SPRINT 2026, Hires 26/27, CSSD…) are deal and season codes, all public
  shows. None is needed: across all of 2026 this box office sold only
  performances — no ice-creams, programmes, touch tours, courses or gift
  items — so **every performance in the building → `theater`**.
- Seating plan → client venue (`plan_venues=True`): only **Camden People's
  Theatre**. Dropped: partner venues used for its festivals (The Place,
  Conway Hall, Wellcome Collection, Shoreditch Town Hall, Old Vic Workrooms,
  Soho Theatre, The Pleasance, Omnibus, Stratford Circus, Rich Mix,
  Ovalhouse, Bloomsbury Studio…) and Online / Zoom / Virtual Theatre.
- Why not `Site(required=True)`: tried. A CPT show page shows ticket links
  only while a performance is on sale, so a required join dropped 8 of 27
  events on 2026-10-24 (sold out / off sale: Trash Salad, Dottie, Bubbly,
  three Trans People Are Awful nights; BUOY and Mothership aren't on the
  what's-on page) — and it would not have dropped anything else, since the
  website lists everything the box office sells.

## Known leaks

- "CPT's Board Game Afternoon" (5 Dec 2026, £5) — a community social, sold
  and listed like any show; no structural signal separates it.
- Past data has occasional "[archive]" / "(digital)" recordings of shows on
  the theatre's own plan (FinancialArrangement "Other", Starting Blocks);
  none in the current window.

## Quirks

- Many one- or two-night runs; ticket tiers are pay-what-you-can bands on
  some nights (band default = the lowest PWYC tier, e.g. "Trans People Are
  Awful Trans Plus Night" shows "£1"; its "[£100 night]" fundraiser "£100").

## Verification

Last verified **2026-10-24**, live: 57 performances, 27 events, 100% priced;
46 link to cptheatre.co.uk, 11 to the Spektrix page (no on-sale ticket links
on their page, or not on the what's-on page). Sharp Edges: 5 perfs 11–14 Nov,
19:00 + Sat 15:00, "£18" — matches its page ("Wed 11 Nov - Sat 14 Nov at 7pm
(3pm matinee on Sat)", "Tickets £12 - £18"; £12 is a concession band).
Cold-start DB: 57 rows.
