# Orange Tree Theatre — source map

Venue slug: `orange-tree-theatre` (London) — 1 Clarence Street, Richmond
TW9 2SA. Rediscoveries and new writing in the round → `theater` (list
`theater`).

Data: Spektrix client `orangetree` (custom domain
`tickets.orangetreetheatre.co.uk`) via `_spektrix.py` (see
`spektrix_SOURCE.md`). No Site join: the show pages on orangetreetheatre.co.uk
embed no Spektrix ids (their "choose a performance" widget loads client-side;
the WordPress REST `show` records carry only first/last day and a
show-category), so events link to the Spektrix event page.

## Curation

- `Type`: **Classical Play** and **Drama New Writing** → `theater`.
  Dropped: **Literary Talks** (Saturday Seminars), **Youth Theatre/Drama**,
  **Children/Family** (schools' Primary Shakespeare), **Chamber & Recitals**
  and untyped events. Chamber & Recitals is, in this client, always the
  "Chamber Music at St Mary Magdalene" series (Constanze, Schubert,
  Solace of Pilgrims; past: Fidelio Trio, Impressions) — held at St Mary
  Magdalene Church (TW9 1SN) though booked on the theatre's own seating plan,
  so it would show at the wrong address. Untyped: OT On Screen streams, short
  courses/labs, Under 30s workshops, Shakespeare Up Close (schools), seminars,
  Sunday Morning Coffee Concerts.
- Seating plan → client venue (`plan_venues=True`): only **Orange Tree
  Theatre**. Dropped: St John's ("Murder in the Cathedral: OT in the Church"
  at St John the Divine, and its seminar), Thomas' College, OT On Screen.

## Known gap

**Cranford** (78 performances, 3 Nov 2026 – 16 Jan 2027, the Christmas main
show) has no `Type` yet, so it is not scraped. Every past and announced main
production carries a Type (a small and quiet light, King Lear, Richard II,
The Vortex, Wives as they were…), so it should appear once the box office
types it. No other structural signal separates it from the untyped
streams/workshops/seminars.

## Verification

Last verified **2026-10-24**, live: 74 performances, 5 plays, 71 priced (the
3 unpriced are performances whose price list answers 404 — off sale), all
Spektrix links, 2026-10-24 → 2027-04-24. King Lear: 31 perfs 15 Feb–10 Apr
2027, 19:30 evenings and 14:00 matinees, "£15–34.50" previews / "£15–69" —
matches its page ("15 February 2027 to 10 April 2027", "Mon 15th Feb 7:30
pm…"). Cold-start DB: 74 rows.
