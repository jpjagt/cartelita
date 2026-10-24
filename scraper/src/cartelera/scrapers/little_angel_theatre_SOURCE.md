# Little Angel Theatre — source map

Source slug: `little-angel-theatre` (London), multi-venue:

| Venue slug | Building | Spektrix venue |
|---|---|---|
| `little-angel-theatre` | 14 Dagmar Passage, N1 2DN | "Little Angel Theatre" |
| `little-angel-studios` | Sebbon Street, N1 2EH | "Little Angel Studios" |

Puppet theatre for children; category `kids` (list `kids`).

Data: Spektrix client `littleangeltheatre` via `_spektrix.py` (see
`spektrix_SOURCE.md`). The building comes from the performance's seating plan
(`plan_venues=True`: `/plans/{planId}` → `/venues`); performances at the
client's other venues (Islington Square, Online Workshop, Vimeo, Little Angel
Workshop, Tall Stories) are dropped. Show pages on littleangeltheatre.com are
joined in: each links its performances as `/book/<numeric instance id>`.

## Curation

The box office's `EventType`: **In-house show** is programme (relaxed
performances are separate in-house-show events and are kept). Dropped:
Family activity (workshops), Children only activity (Puppet Playcation),
Adult short/term course.

## Quirks

- The website's per-show page states the building ("At Little Angel
  Studios"); it agrees with the plan → venue mapping.
- `annotations`: instance `attribute_InstanceInfo` carries the
  performance's access note ("BSL Performance", "Relaxed Performance"),
  taken verbatim (`annotation_attrs`; live values 2026-10-24 are only
  these). `ConfirmationText` repeats it for the confirmation email — not
  used.

## Verification

Last verified **2026-10-24**, live: 236 performances (Studios 119, Theatre
117), every one priced; all link to the venue's own show page. The Pied
Piper: A Rat's Tale — 11:00/14:00/16:00, "£16", Little Angel Studios —
matches its page ("£16.00 Adult", "At Little Angel Studios"). Cold-start DB:
236 rows.
