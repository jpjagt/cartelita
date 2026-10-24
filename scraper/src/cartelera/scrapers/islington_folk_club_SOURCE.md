# Islington Folk Club — source map

Venue slug: `islington-folk-club` (London) — the club meets upstairs at
the Brewhouse & Kitchen, 2a Corsica Street, Highbury N5 1JJ (Thursdays
except July, August and the Christmas break). Category `folk` (list
`folk`). Coordinates are set explicitly from the club's own OpenStreetMap
link (51.546256, −0.102114).

## Data source

A static hand-written site, **windows-1252** (decode the bytes yourself;
the server sends no charset), plain httpx with `CARTELITA_COMPAT_UA`:

- `https://www.islingtonfolkclub.co.uk/programme.html` — tables of
  `Date | Artist | Note` rows ("29th October 2026" | "Louise and Chris
  Rogan" | blurb); one table per season block.
- `https://www.islingtonfolkclub.co.uk/ifc.html` (where `/` redirects) —
  club-wide facts in prose: "the evenings begin at 8pm (doors open by
  7.30)" → start time; "Admission, payable on the door by cash or card is
  £10.00 (£8.00 for concessions)" → `gbp_price` → "£10". Either missing →
  None.

## Curation

Single-genre club → folk. Rows whose Artist cell is "Club closed" (the
table's Christmas-break markers, 24 and 31 Dec) are not events and are
skipped; the Christmas Party and Singaround is a club night and kept.

## Fields

`title` = Artist; `description` = Note; `start_date` = Date; `source_url`
= the programme page (no per-night pages); `external_id` = `ifc-<date>`
(one night per date).

## Verification

Last verified **2026-10-25** via HTTP: 12 nights (29 Oct 2026 – 28 Jan
2027, all Thursdays), 100% priced/timed. The home page's "Our next guest
29th October 2026 Louise and Chris Rogan" matches the scraper's first
row (29 Oct 20:00 "£10"). Cold-start DB: 12 rows.
