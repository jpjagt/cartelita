# The Yard Theatre — source map

Venue slug: `the-yard-theatre` (London) — 2a Queen's Yard, White Post Lane,
Hackney Wick E9 5EN. New work → `theater` (list `theater`).

Data: Spektrix client `theyard` via `_spektrix.py` (see `spektrix_SOURCE.md`).
`source_url` = the event's `webUrl` (its page on theyardtheatre.co.uk).

## Curation

The client has no genre/type attribute (only `EventNameShort`,
`QualifiesForYardCard`). Curation is the box office's own **`webUrl`**
field: the Yard fills it with the event's page
(`https://www.theyardtheatre.co.uk/events/<slug>`) for every public show and
leaves it empty for what it sells but doesn't programme. Kept: runs (Lear,
There's Something About Adam Black, Mrs Dalloway) and Live Drafts readings.
Dropped (2026-10-24): "Lear: The Gala" (fundraiser, no webUrl). Earlier
research saw "Name a Seat" on this client — the same rule drops it.

No `Site` join: the Next.js show pages carry Spektrix *short codes*
(`"spektrixId":"LEAR"`, `"DIRTY"`) rather than API ids, and `webUrl` already
is the show page.

## Quirks

- Price lists include a premium "Legend" band (Lear: £150–300 standard
  band), so the band-default range reads "£10–150" … "£15–300" for Lear.
- Mrs Dalloway's page copy says previews start 7:30pm; the box office and
  the page's own structured data both say 19:00 — we follow the box office.

## Verification

Last verified **2026-10-24**, live: 120 performances, 6 events, 100% priced,
all linking to theyardtheatre.co.uk, 2026-10-30 → 2027-04-10. Mrs Dalloway:
35 perfs 10 Mar–10 Apr 2027, 19:00 + 14:30 matinees — matches its page ("10
March - 10 April 2027", "Monday - Saturday, 2:30pm & 7.00pm"). Cold-start
DB: 120 rows.
