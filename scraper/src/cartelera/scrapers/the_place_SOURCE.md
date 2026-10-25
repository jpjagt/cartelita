# The Place — source map

Venue slug: `the-place` (London) — 17 Duke's Road, Euston WC1H 9PY.
Contemporary dance theatre (and London Contemporary Dance School).
Categories `dance` (list `dance`) and `kids` (list `kids`, Family Programme),
each list whitelisted to its category.

Data: Spektrix client `theplace` (system.spektrix.com) via `_spektrix.py`
(see `spektrix_SOURCE.md` for endpoints and field mapping): one
`spk.scrape` call with a site join, a title override and a `price_bands`
filter (the two venue quirks below).

## Curation (the client's own labels)

All four must hold:

| Attribute | Kept | Dropped (why) |
|---|---|---|
| `WebsiteListing` | Performance | Class (C&C drop-in classes, Pro Class, LCDS info sessions, Butoh intensive), Children and Youth Dance, blank (enrolment fees) |
| `Type` (label before the finance code) | Theatre Programme, Family Programme (→ dance + kids), Resolution (the festival's triple bills), LCDS FRAMERUSH (school shows: Repertory Project, Mixed Bill, Percolator — its info sessions are `WebsiteListing` Class) | Resolution Workshops (artist-development sessions), LCDS ad-hoc Workshops (open days, experience days), Theatre External Hire (ZooNation academy show), CYD/C&C fees |
| `WebsiteVenue` | at The Place | off-site (LCDS experience days in Newcastle/Nottingham/Cornwall, over-60s classes) |
| `TicketName1` | anything else | "TOUCH TOUR" — touch tours carry every label of their show (Performance / Theatre Programme / at The Place); the client's ticket-name field is the only thing that tells them apart |

Kept although borderline: the Peggy Hawkins Fundraising Gala (a gala
performance), Camden Youth Dance Festival (a public performance).

A `Site(required=True)` join doesn't curate here: the site lists open days and
info sessions too, and books touch tours from the show's own page.

## Fields / quirks

- `title`: event `name` minus the internal season prefix ("Autumn/ Winter 26: ",
  "Spring/Summer 2027: ", "Autumn/Winter 2026: " — regex `_SEASON`); display
  only. "Res 27: <artists>" (Resolution) is left as the venue names it.
- `source_url`: show pages on theplace.org.uk (the what's-on page's
  `/events/<slug>` links) book each performance as
  `/book/instance/<numeric instance id>`; the shared `Site` join collects
  those ids and picks each event's page. **The join is links-only**: if the
  what's-on listing can't be fetched, the helper logs a warning and every
  event links to the Spektrix event page (`Site` without `required`, see
  `spektrix_SOURCE.md`) — which is what happens in production (below).
  Shows not (yet) on the site —
  Resolution 2027, most of spring 2027 — and performances whose online
  booking has closed fall back to the Spektrix event page.
- `price`: each price list has a "Standard" band beside concession bands that
  are also flagged `isBandDefault` ("LCDS Student" £5, "Wheelchair spaces"),
  so the shared rule gave "£5–22" where the site says "Standard £22, concs
  £18". `standard_band` (the helper's `price_bands` filter) keeps the
  Standard band only; a price list without one falls back to the shared
  rule.

## Verification

Last verified **2026-10-24**, live: box office 100 events / 287 instances →
kept **47 events / 81 performances** (2026-10-24 → 2027-04-24), 81/81 priced
(100%), 40 linked to the venue's page, 41 to the Spektrix page; categories
dance 63, dance+kids 18.
Field check, Marikiscrycrycry – Hang Time vs
theplace.org.uk/events/autumn-winter-26-hang-time: 29/30/31 Oct 19:30 (page's
booking links = the three instance ids), "£22" (page: "Standard £22, concs
£18"), venue "At The Place" — match. Starchitects Save Santa: 11 perfs 16–23
Dec, dance + kids, "£18".
Cold-start DB: 81 rows (no collapsed occurrences).

## Production (Hetzner IP), 2026-10-25
theplace.org.uk answers the production server with a Cloudflare managed
challenge on every path (httpx, curl_cffi, headless browser — no
clearance), and it has no search index or other open listing (Craft, no
Typesense). Curation is the Spektrix client's own labels, so only the links
are affected: in prod all 80 performances link to the Spektrix event page
(locally 40 link to theplace.org.uk). Verified from prod with the new code:
80 performances, identical to local except those 40 `source_url`s.
