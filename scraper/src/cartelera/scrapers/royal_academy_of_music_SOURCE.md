# Royal Academy of Music — source map

Venue slug: `royal-academy-of-music` (London) — Marylebone Road NW1 5HT.
Conservatoire concerts, opera and masterclasses, many free; category
`classical` (list `classical`).

Data: Spektrix client `royalacademyofmusic` on `https://ticketing.ram.ac.uk`
via `_spektrix.py` (see `spektrix_SOURCE.md`), joined to the site's search
index (curation) and plan venues.

## Curation

The client's only event attribute is `Venue` (the room: Duke's Hall, Angela
Burgess Recital Hall, Susie Sainsbury Theatre, Concert Room); no instance
attributes. It doesn't separate ancillaries — "Programme" (printed
programmes, £4, 9 instances alongside the Susie Sainsbury Theatre operas)
has a room like any concert. So:

- **Listed by the Academy** (`page_ids=…, listed_only=True`): only events
  the site lists are kept. The what's-on page renders by script from the
  site's Typesense index `ram_main_production` (`spk.SearchIndex`; key and
  nodes in `spektrix_SOURCE.md`). Its `type = events` documents (87 on
  2026-10-25) carry `uri` (`/events/<slug>`) and `emImportData.importId` —
  the numeric Spektrix id the page was imported from (an instance id, or
  the event id) — so `spk.search_page_ids` gives the join without fetching
  ram.ac.uk (one request instead of one per event page). This drops
  "Programme" (never listed). (Until 2026-10-25: the sitemap + every event
  page's embedded ids; same result, but ram.ac.uk challenges the production
  server.)
- Building: seating plan → client venue; only "Royal Academy of Music" is
  kept (the client also has Wigmore Hall, St John's Smith Square, Snape
  Maltings, Southbank Centre, Regent Hall, Crazy Coqs, Greyfriars Kirk —
  partner venues; none had performances in the window).
- Category: every listed event at the Academy → classical.

**Known imprecision.** The website's own categories (Lunchtime concerts,
Orchestra, Opera, Jazz, Masterclasses, Talks and Conferences, Musical
Theatre, Free Events…) exist only in its Typesense search index (a
third-party API, now read for the join anyway: `eventCategories`, e.g.
["Opera"]), not on the event pages or in Spektrix. A follow-up could map
them (Jazz → jazz) — not done here, output kept identical. So Academy jazz ("Jazz Ensembles", 3 perfs), the masterclasses
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

## Production (Hetzner IP), 2026-10-25
ram.ac.uk answers the production server with a Cloudflare managed challenge
on every path (sitemap and event pages; the browser helper gets no
clearance either), so the sitemap join failed the run. The Typesense index
answers it. Local before/after: 51 performances, identical (ids, URLs,
prices). Verified from prod with the new code: the same 51.
