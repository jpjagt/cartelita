# Arcola Theatre — source map

Venue slug: `arcola-theatre` (London) — 24 Ashwin Street, Dalston E8 3DL.
Fringe/international theatre (Studios 1 and 2) → `theater`; its summer opera
festival Grimeborn → `classical`. Lists `theater` and `classical`, each
whitelisted to its category.

Data: Spektrix client `arcolatheatre` (custom domain
`boxoffice.arcolatheatre.com`; `system.spektrix.com` answers too) via
`_spektrix.py` (see `spektrix_SOURCE.md`). Show pages on arcolatheatre.com are
joined in (`Site("https://www.arcolatheatre.com/whats-on/", …/event/<slug>/)`):
each embeds its performances' full Spektrix ids. During Grimeborn the
what's-on page links the festival page rather than each opera, so those may
fall back to the Spektrix event page.

## Curation

- `Genre`: **Theatre** is programme. Dropped: **Workshop** (writing
  workshops, youth theatre terms).
- Seating plan → client venue (`plan_venues=True`): only **Arcola Theatre**.
  Dropped: **Workshops** (the participation strand — Arcola Youth Theatre
  terms, 50+ Serious Play; note "2026: AYT Tuesday Autumn Term" is coded
  Genre=Theatre, so the venue is what drops it), Food, Earth Hackney, Arcola
  Outside, Studio 1 (legacy venue record; current Studio 1 shows are on the
  "Arcola Theatre" venue — `attribute_Location` says the room).
- `Festival` = **Grimeborn** → `classical` (checked on the July–September
  2026 programme: 11 Grimeborn operas, all Genre=Theatre on the Arcola Theatre
  venue); else `theater`.

## Quirks

- Event names carry an internal season prefix ("2026: The Master Builder",
  "2027: Incident at Vichy"); `title()` strips a leading `YYYY: `. Grimeborn
  names ("Grimeborn 2026: Rinaldo") are left as they are.
- `attribute_Location` (Studio 1 / Studio 2 / Rehearsal Room…) is the room;
  not used (the plan venue already separates stage from participation).

## Verification

Last verified **2026-10-24**, live: 141 performances, 6 shows, all priced,
all linking to arcolatheatre.com, 2026-10-24 → 2027-02-27. The Master
Builder: 32 perfs 24 Oct–21 Nov at 14:30/19:00/19:30, "£15–39" — matches its
page ("16 Oct - 21 Nov 2026", "£15 - £39", "Venue: Studio 1", "2.30pm, 7pm &
7.30pm"). Cold-start DB: 141 rows (no collapsed occurrences).
