# New Diorama Theatre — source map

Venue slug: `new-diorama-theatre` (London) — 15-16 Triton Street, Regent's
Place NW1 3BF. Category `theater` (list `theater`).

Data: Ticketsolve feed
`https://newdiorama-tickets.newdiorama.com/shows.xml` (custom domain) via
`_ticketsolve.py` (see `ticketsolve_SOURCE.md`).

## Curation

The feed is the theatre's own box office for its single auditorium and has
no `event_category`; every show at feed venue "New Diorama Theatre" →
theater. Checked 2026-10-25: 2 shows / 31 performances, no ancillaries.
newdiorama.com's what's-on also lists touring and West End transfers
(The Shivers — national tour; Operation Mincemeat — West End/Broadway);
those are not sold through this feed and are not at the venue.

## Fields

As the helper. Prices per performance differ: previews "Standard £13" →
"£13", main run "General Admission £19" → "£19", Pay What You Can
Saturdays (£5/£10/£14/£19/£25) → "£5–25". Annotations: preview, pay what
you can, relaxed, captioned. `source_url` is the Ticketsolve performance
page (the newdiorama.com show page embeds the show id, not joined).

## Verification

Last verified **2026-10-25** via HTTP cross-check with
newdiorama.com/whats-on/orlando: "10 Nov - 12 Dec 2026, Tue - Sat 7.30pm,
Sat matinees 3pm; Previews (10 - 17 Nov) £13 full price …; Pay What You
Can Saturdays (14 Nov); Main Run £19" → scraper 29 performances, 10 Nov
19:30 "£13" (preview), 14 Nov "£5–25" (pay what you can), 18 Nov+ "£19"; 2
sold out. Cold-start DB: 29 rows.
