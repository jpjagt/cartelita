# Royal Court Theatre — source map

Venue slug: `royal-court-theatre` (London) — Sloane Square, SW1W 8AS. New
writing; category `theater` (list `theater`).

Data: Spektrix client `royalcourt` on its custom domain
(`https://tickets.royalcourttheatre.com/royalcourt/api/v3`) via `_spektrix.py`
(see `spektrix_SOURCE.md` for endpoints and field mapping), joined to the
site's search index `royalcourttheatre_main_production` (`spk.SearchIndex`,
the Typesense index behind royalcourttheatre.com's search; key and nodes in
`spektrix_SOURCE.md`). Its `type = events` documents (15 on 2026-10-25:
every published `/events/<slug>` page, incl. past ones) carry `title` and
`uri` but **no Spektrix id**, so the join is the event's **exact name**
(`spk.title_key`: whitespace and case only, never fuzzy; module `Listing`).
Spektrix names and site titles match exactly for every show (Monument,
Blood of my Blood, The Afronauts, Man to Man). (Until 2026-10-25 the join
was the sitemap + the Spektrix ids each show page embeds — royalcourttheatre.com
challenges the production server, see below.)

## Curation

The client has no genre/type attribute, so two structural signals:

1. **Listed on the venue's site** (named by the search index): drops the box
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
  (the Royal Court's 10p standing tickets, sold on the day) as a band
  default. It is a real ticket, but the theatre's own price statement
  leaves it out ("Tickets: £15 - £74.50" on the show page, 2026-10-24), so
  the module does too (`price_bands=seated_band`): Downstairs shows read
  e.g. "£25–74.50" (band D £25 – band A £74.50, plus the £25 "35 and
  Under" band) instead of "£0.10–74.50". The site's £15 low end is the
  Monday price: Monday performances are £15 throughout (the site's "£15
  Mondays") and come out as "£15". A press night whose only paid ticket is
  the standing one (seats go to press; access tickets £0) keeps "£0.10"
  (the filter falls back to the whole list when it leaves no paid price).
- (Show pages show no booking ids on a show's last day / when sold out; the
  old show-page join dropped those performances — Man to Man, 24 Oct. The
  name join keeps them.)
- The risk of a name join: a show renamed on one side only drops out (a
  count drop the health check flags), never a wrong event in.
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

## Production (Hetzner IP), 2026-10-25
royalcourttheatre.com answers the production server with a Cloudflare
managed challenge on every path (sitemap, what's-on, show pages; the
browser helper gets no clearance), so the required sitemap join failed the
run. The Spektrix client alone can't replace it (test events and touch
tours sit in the Jerwood rooms, unpublished shows are only "not on sale"),
so the site listing stays the curation, read from the Typesense index,
which answers prod. Local before/after: 97 performances, identical (ids,
URLs, prices). Verified from prod with the new code: the same 97.
