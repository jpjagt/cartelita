# Polka Theatre — source map

Venue slug: `polka-theatre` (London) — 240 The Broadway, Wimbledon SW19 1SB.
Children's theatre; category `kids` (list `kids`).

Data: Spektrix client `polka` via `_spektrix.py` (see `spektrix_SOURCE.md` for
endpoints and field mapping). Show pages on polkatheatre.com are joined in
(`Site("https://polkatheatre.com/whats-on/", …/event/<slug>/)`): each embeds
its performances' full Spektrix ids, so events link to the venue's own page.
Shows Spektrix sells before the website lists them (2026-10: Shiny, Big Red
Bath) fall back to the Spektrix event page.

## Curation

The box office's `Type` attribute: **Show** is programme. Dropped: Holiday
Workshop, Drop-in Workshop, School Workshops, Saturday Club, Ancillary Event
(ice-cream pre-orders per show), Other ("Secure My Booking" — 383 instances —
touch tours, CPD days, Young Ambassadors).

## Quirks

- Prices: adult and child tickets share the band price; Peter Pan and the
  Christmas shows have real seating bands ("£10–29.50"). The website says
  "Tickets from £10" where we show the top band ("£19") — the house rule.
- 47 of 397 performances (2026-10-24) have no price: their price lists answer
  404 because no performance on them is on sale yet (next spring's shows).

## Verification

Last verified **2026-10-24**, live: 397 performances, 14 shows, 2026-10-24 →
2027-04-24. Toto (16 perfs, 11:00/14:00 daily 24 Oct–1 Nov, "£19") matches
polkatheatre.com/event/toto/ ("Saturday 24 October – Sunday 1 November",
"Tickets from £10"). Cold-start DB: 397 rows (no collapsed occurrences).
