# Sadler's Wells (source `sadlers-wells`, 3 venues)

Venues (buildings): `sadlers-wells` (Sadler's Wells Theatre + Lilian Baylis
Studio, Rosebery Ave), `peacock-theatre` (Holborn), `sadlers-wells-east`
(Stratford). Category: dance (all; the site has no family label).

## Data sources
- Listing: `https://www.sadlerswells.com/whats-on/` + `/whats-on/page/N/`
  (`.c-pagination`), 16 cards a page; `.c-event-card a.c-event-card__cover-link`
  → show page, title = its `.u-hidden-visually` text ("Company - Show").
- Show page `.c-event-instance` (one per performance): `__anchor#instance-<id>`
  (external_id), `__date` ("Tuesday 3 November", no year), `__time`
  ("7:30 pm"), `__venue-name` (stage → venue), `__price` ("From: £15.00" →
  "from £15"; £0.00 → "free"), `__actions` ("Sold out" / "Onsale 28 October"
  / booking link `data-booking-url=https://my.sadlerswells.com/<prod>/<perf>`).
  `.c-access-type` blocks link `#instance-<id>` → annotations (relaxed /
  audio described / BSL interpreted / touch tour …).
- TNEW (`my.sadlerswells.com`, see tnew_SOURCE.md): cross-check only — the
  exact date of every linked performance and its sold-out status. Unlinked
  blocks (sold out, not yet on sale) get the year from their weekday (first
  year whose calendar puts that day on that weekday, not >7 days past).
  Website primary because sold-out performances lose their TNEW link (Kabuki:
  both sold out, no link) and TNEW sells things the site doesn't list. A TNEW
  failure only logs a warning.
- Window: today → +183 days (Singin' in the Rain, Ballet Shoes, Rambert's
  It's a Sin are listed but beyond it).
- Image: the TNEW listing image of the production (when any performance is
  linked).

## Curation
Kept: every performance block of a show page the what's-on lists — the
venue's public programme. Never seen (not listed on the site, only sold in
TNEW): DF classes, Artist-Led Sessions, touch tours, AD headsets, Stagecoach,
hires. **Owner review**: the listing also carries two free participatory
strands — Culture Club (Friday talks/workshops for 18+, 13 dates) and Family
Freestyle (sessions for ages 2–4, Sadler's Wells East, 13 dates). There is no
structural label separating them (TNEW productTypeId 5 also covers the
performance Repertório N.3), so they are kept as dance.

## Verification (2026-10-25, independent regex read of the live pages)
313 events (sadlers-wells 140, sadlers-wells-east 105, peacock-theatre 68);
priced 99.7%. Cold-start DB rows = 313. Checked: Big Live – The Great Gatsby
2027-04-03 19:00, Sadler's Wells Theatre, "From: £15.00" = ours (19:00, from
£15; TNEW 18:00 UTC = 19:00 BST); The Snowman 2027-01-03 14:30 Peacock "From:
£30.00" = ours; Jasmin Vardimon – Lullaby 2027-02-27 19:30 Sadler's Wells East
£15 = ours. Weekday-derived dates equal TNEW dates for every linked block.
