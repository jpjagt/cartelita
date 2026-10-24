# Unicorn Theatre — source map

Venue slug: `unicorn-theatre` (London) — 147 Tooley Street, London Bridge
SE1 2HZ. Theatre for children and young people; category `kids` (list
`kids`).

Data: Spektrix client `unicorntheatre` (`system.spektrix.com`) via
`_spektrix.py` (see `spektrix_SOURCE.md` for endpoints and field mapping).

## Curation

- Event `EventType`: Unicorn Production / Co-production / Visiting Company
  → kids. That is every event the client sells (checked back to 2024: 14
  events, no ancillaries); anything else is dropped.
- Instance `Owner`: **Public** and **Press Night** are kept (press nights are
  on general sale, e.g. Santa's First Christmas 14 Nov). **Schools**
  performances (booked by school groups only; ~1/3 of all instances) are
  dropped.
- Instance `Location`: "Unicorn Theatre (Weston)" / "Unicorn Theatre (Clore)"
  (the two auditoria). Anything else (the client's "Digital theatre in your
  home" venue) is dropped.

## Fields / quirks

- `source_url`: the Spektrix event page. unicorntheatre.com show pages load
  their dates by script and embed no Spektrix ids (checked: no full ids, no
  `/book/<id>`, no `EventInstanceId=`), so no site join.
- Price varies per performance (peak/off-peak price lists). Baby shows (Home
  Song) sell a "Combined Ticket (1 Adult + 1 Child)" as the band default, so
  the price shown (£25.50 / £20.50) is the pair's price.
- Pocket Money's remaining public performances are off sale (price lists
  404 → price unknown) and the show is no longer on the website.
- Unicorn's access flags use their own names (`BSL`, `PreviewPerformance`,
  `SensoryAdapted`), which the helper's `ACCESS_FLAGS` doesn't know, so
  they're not surfaced (only `Captioned` / `AudioDescribed` are).
- `AgeGuide` (e.g. "4+") is filled for one event only; not surfaced.

## Verification

Last verified **2026-10-24**, live: 187 performances (292 instances − 105
Schools), 8 shows, 172 priced (92%; the 15 unpriced are Pocket Money). Home
Song: 10:00/11:30/13:30 from 24 Oct to Sun 8 Nov — matches
unicorntheatre.com/events/home-song-2026 ("Fri 2 Oct – Sun 8 Nov") and the
Spektrix event page (same times per day). Cold-start DB: 187 rows.
