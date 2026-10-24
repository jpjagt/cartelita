# Royal Academy of Music — source map

Venue slug: `royal-academy-of-music` (London) — Marylebone Road NW1 5HT.
Conservatoire concerts, opera and masterclasses, many free; category
`classical` (list `classical`).

Data: Spektrix client `royalacademyofmusic` on `https://ticketing.ram.ac.uk`
via `_spektrix.py` (see `spektrix_SOURCE.md`), with a required site join and
plan venues.

## Curation

The client's only event attribute is `Venue` (the room: Duke's Hall, Angela
Burgess Recital Hall, Susie Sainsbury Theatre, Concert Room); no instance
attributes. It doesn't separate ancillaries — "Programme" (printed
programmes, £4, 9 instances alongside the Susie Sainsbury Theatre operas)
has a room like any concert. So:

- **`Site(required=True)`**: only events whose page on ram.ac.uk embeds their
  Spektrix ids are kept. The what's-on page renders by script (Typesense),
  so the listing is **`https://www.ram.ac.uk/sitemap.xml`**, which links
  every event page `https://www.ram.ac.uk/events/<slug>` (69 on 2026-10-24;
  each page embeds the event's full Spektrix id, `134001ABB…`). This drops
  "Programme" (never listed). It costs one request per event page.
- Building: seating plan → client venue; only "Royal Academy of Music" is
  kept (the client also has Wigmore Hall, St John's Smith Square, Snape
  Maltings, Southbank Centre, Regent Hall, Crazy Coqs, Greyfriars Kirk —
  partner venues; none had performances in the window).
- Category: every listed event at the Academy → classical.

**Known imprecision.** The website's own categories (Lunchtime concerts,
Orchestra, Opera, Jazz, Masterclasses, Talks and Conferences, Musical
Theatre, Free Events…) exist only in its Typesense search index (a
third-party API with a key in the JS bundle), not on the event pages or in
Spektrix. So Academy jazz ("Jazz Ensembles", 3 perfs), the masterclasses
(public, £8), talks ("Doctoral Symposium", "Perspectives on The Mulliner
Book") and the musical-theatre tribute ("Georgie") are all `classical`.

## Fields

- `source_url`: the event page on ram.ac.uk from the site join (all kept
  events have one); `webUrl` is filled for one event only.
- `price`: price list (helper). Free events come through as "free" (lunchtime
  concerts, recitals — the site says "Free - booking required").

## Verification

Last verified **2026-10-24**, live: 51 performances, 44 events, 100% priced
(25 free). Capriccio — Mon 23, Wed 25, Thu 26, Fri 27 Nov 7:00pm, "£20–50" —
matches ram.ac.uk/events/capriccio ("£20-£50 (CONCs £20)", same four dates).
Trio Avant — Tue 3 Nov 1:00pm, "free" — matches its page ("Free - booking
required"). Cold-start DB: 51 rows.
