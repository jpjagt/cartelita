# Southwark Playhouse — source map

Source slug: `southwark-playhouse` (London), multi-venue:

| Venue slug | Building | Spektrix venue |
|---|---|---|
| `southwark-playhouse-borough` | 77-85 Newington Causeway, SE1 6BD | "Southwark Playhouse Borough" |
| `southwark-playhouse-elephant` | 1 Dante Place, Elephant Park, SE11 4RX | "Southwark Playhouse Elephant" |

Fringe theatre and new musicals → `theater` (list `theater`).

Data: Spektrix client `southwarkplayhouse` via `_spektrix.py` (see
`spektrix_SOURCE.md`). The building comes from the performance's seating plan
(`plan_venues=True`); the client has no other venues. Production pages are
joined in: the homepage (`https://southwarkplayhouse.co.uk/`; `/whats-on/`
redirects there) links every production as `/productions/<slug>/`, and each
page embeds the event's full Spektrix id (`<var hidden id="spektrixid">`) —
an event id, present whether or not performances are on sale.

## Curation

The client has no genre/type attribute (only `ProducerName`), so curation is
the website: `Site(required=True)` — only events with a production page are
kept. Dropped (2026-10-24): "Black Writers Collective (2026/27)" (3 sessions
at Elephant, sold but not listed — a writers' group).

## Verification

Last verified **2026-10-24**, live: 365 performances (Borough 272, Elephant
93), 10 productions, 100% priced, all linking to the venue's own page.
NERO: 39 perfs 2 Nov–5 Dec at Elephant, 19:00 + 14:30 matinees; "£10" (2
Nov), "£16" ×3, "£20–50" — matches its page ("Venue: Elephant", "2 Nov - 5
Dec 2026", "Monday – Saturday: 7pm, Thursday & Saturday: 2.30pm", "Standard
from £20 | Previews £16 | Pioneers' Preview (2 Nov) £10"). Cold-start DB: 365
rows.
