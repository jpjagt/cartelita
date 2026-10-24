# Royal Court Theatre — source map

Venue slug: `royal-court-theatre` (London) — Sloane Square, SW1W 8AS. New
writing; category `theater` (list `theater`).

Data: Spektrix client `royalcourt` on its custom domain
(`https://tickets.royalcourttheatre.com/royalcourt/api/v3`) via `_spektrix.py`
(see `spektrix_SOURCE.md` for endpoints and field mapping). Show pages on
royalcourttheatre.com are joined in with `Site(..., required=True)`; the
listing is **`https://royalcourttheatre.com/sitemap.xml`**, not the what's-on
page: the what's-on page drops a show on its final day (Man to Man, 24 Oct)
while the sitemap lists every published `/events/<slug>` page. Show pages
embed their performances' full Spektrix ids (booking buttons), so events
link to the venue's page.

## Curation

The client has no genre/type attribute, so two structural signals:

1. **Listed on the venue's site** (`Site(required=True)`): drops the box
   office's test events ("Poppy Test Event", "Z - 2627 Test", "Touch Tour -
   TEST" — all in Jerwood Theatre Downstairs), the per-show touch tours ("The
   Afronauts - Touch Tour"; not on any show page) and shows the box office
   holds before the website publishes them (2026-10-24: Purpose, The Apology,
   We're Gonna Kill Billy, War Face — no page, not on sale, not in the
   sitemap; they appear once their page goes up). There is no season page or
   calendar listing them (the calendar is per-day and only shows on-sale
   performances).
2. **`TicketVenue1` = Jerwood Theatre Downstairs / Jerwood Theatre Upstairs**
   (the two auditoriums). The site also lists non-performance events, dropped
   here by their room: Book Club, First Words, Directors' Night (Balcony Bar),
   Writers' Card career surgeries / canteen (Bar & Kitchen, Zoom), Backstage
   Tour (room = the whole building). Off-site: 70th Anniversary Bowling Party
   (Bloomsbury Lanes), Giant screening (May Fair Hotel); online: Zoom.

`TicketVenue2` (the address) was the research note's proposal for off-site
rows, but it doesn't drop tests or bar events; the room does.

## Quirks

- Prices: the Downstairs price lists carry a **"Standing" band at £0.10**
  (the Royal Court's 10p standing tickets) as a band default, so Downstairs
  shows read "£0.10–74.50" where the site says "£15 - £74.50". The helper's
  `price_text` has no band filter; left as is (it is a real ticket) and
  reported as a helper gap. Monday performances are £15 throughout (the
  site's "£15 Mondays") and come out as "£15".
- A show page shows no booking ids on its last day / when sold out (Man to
  Man, 24 Oct): its remaining performances drop out with it.
- One Monument performance (9 Dec, 19:00) has no price: its price list
  answers 404 (not on sale online).
- `Location` (instance attribute) repeats the room per performance; unused.

## Verification

Last verified **2026-10-24**, live: 99 performances, 3 shows (Blood of my
Blood, The Afronauts, Monument), 98/99 priced, all with royalcourttheatre.com
URLs. Monument: 42 performances 3 Dec–23 Jan, 19:45 evenings / 18:45 Sat /
14:00 matinees, £15 Mondays, top £30 — matches the show page ("Thu 3 Dec 2026
– Sat 23 Jan 2027", "Tickets: £15 - £30", Jerwood Theatre Upstairs). The
Afronauts top price £74.50 matches "£15 - £74.50". Cold-start DB: 99 rows
(no collapsed occurrences).
