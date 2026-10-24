# St Martin-in-the-Fields — source map

Venue slug: `st-martin-in-the-fields` (London) — Trafalgar Square WC2N 4JJ
(church and crypt). Categories `classical` and `kids` (family concerts), each
its own list, whitelisted to that category.

Data: Spektrix client `stmartininthefields` on
`https://tickets.stmartin-in-the-fields.org` via `_spektrix.py` (see
`spektrix_SOURCE.md`). No site join: the what's-on page is a script template
(post ids + instance ids in JS arrays, no show links) and show pages
(`/whats-on/<slug>/`) embed no Spektrix ids; `webUrl` is empty. Events link
to the Spektrix event page.

## Curation (the client's own attributes)

`Category` must be Music, `Genre` must name a genre (not "Not Applicable"),
and `SubCategories` decides:

| SubCategories | → |
|---|---|
| Masterworks, Lunchtime Concerts, Choral Discovery Concerts, Christmas (St Martin's Voices carol services etc.), Easter Festival of Music, Sounds of St Martin's, Crypt Close-Up | classical |
| Family | classical + kids |
| **Candlelight Concerts** (~50 events: Four Seasons / Mozart Requiem / Messiah "by Candlelight", the tourist series) | dropped |
| Crypt Live (Motown, Aretha, Sinatra, Nashville, West End nights — tribute/cabaret; `Genre` "Not Applicable" except one Sinatra tribute tagged Jazz) | dropped — no jazz programme here, so nothing goes to the jazz list |
| Come and Sing (participatory), Contemporary (one singer-songwriter), Silent Disco | dropped |

Other `Category` values are dropped: Lectures & Courses ("Here I Stand"
lectures and their livestreams), Ancillary Sales (Cushion Hire — 141
instances —, Lunchtime Meal, Crypt Lates food, Christmas café), Special
Events (discos, Young Voices come-and-sing).
The `Genre` gate removes two Masterworks items with no genre: "Liza Sings
Streisand" (cabaret) and a Darbar Indian-music recital (a loss, but
unlabelled).

Labels are taken as given: a few non-series concerts with "Candlelight" in the
name (Ex Cathedra, the ASMF Bach St John Passion, "Christmas Classics by
Candlelight" under Christmas) are kept — the venue files them outside its
Candlelight series.

## Quirks

- Prices are seating bands A–F incl. restricted / no-view seats (£10), so most
  concerts show a range ("£10–30").

## Verification

Last verified **2026-10-24**, live: box office 132 events / 359 instances →
kept **54 events / 72 performances** (2026-10-24 → 2027-04-23), 72/72 priced;
classical 60, classical+kids 12. All link to the Spektrix page.
Field check, BBC Singers: Songs of Farewell vs
stmartin-in-the-fields.org/whats-on/bbc-singers-songs-of-farewell/: "Friday 13
November, 7:30pm", "Tickets: £10, £16, £20, £25, £30" vs ours 2026-11-13 19:30
"£10–30" — match.
Cold-start DB: 72 rows.
