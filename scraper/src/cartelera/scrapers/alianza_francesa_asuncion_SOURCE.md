# Alianza Francesa de Asunción — source map

Venue slug: `alianza-francesa-asuncion` (Asunción) — Mcal. Estigarribia 1039
c/ EE.UU. (Sala Molière). Categories film, theater (whitelisted memberships).

Own site: `https://alianzafrancesa.edu.py` — WordPress + **Modern Events
Calendar** (MEC v7). The `/agenda-cultural/` page's list renders nothing
server-side useful ("¡No hay eventos!" when the month's batch isn't up), so we
use MEC's machine-readable endpoints (httpx, Cartelita browser UA):

1. `GET /wp-json/wp/v2/mec-events?per_page=50&_fields=id,link,date` — event
   posts, newest first. No event dates here (MEC keeps them in post meta).
2. `GET <link>?method=ical&id=<id>` — MEC's per-event iCalendar export.

Events are posted a few weeks ahead in monthly batches (e.g. the September
films were posted 16 Sep), so only posts published in the last 150 days are
fetched (~10–20 iCal requests per run), and only occurrences from today
(Asunción) on are emitted.

## Fields (from the iCal VEVENT)

| Field | Source |
|---|---|
| `title` | `SUMMARY` ("AF Cine – Les Félins") |
| `start_date`/`start_time` | `DTSTART` — **UTC** ("20260929T220000Z") → converted to America/Asuncion (19:00). `VALUE=DATE` → no time. |
| `source_url` | `URL` (the post link) |
| `description` | `DESCRIPTION` (escapes undone) |
| `image_url` | `ATTACH;FMTTYPE=image/…` |
| `external_id` | post `id` (one post = one screening; no RRULEs seen) |
| `price` | none: the posts only link to the ticket shop (extranet) → None |
| `annotations` | other CATEGORIES (e.g. "Festival", "comedia") minus "arte" |

## Curation (the calendar's own categories)

- Programme: `Cine` → film, `Teatro` → theater.
- Vetoed by `Charla` (lecture cycles, talk + documentary evenings, EXPYFEST)
  and `Feria de países` (Fiesta de la Francofonía fair).
- Not programme (no programme label): La Terrasse (DJ sets / música garden
  party), Fiesta de la Música, philosophy lectures (Biblioteca/Mediateca),
  poetry evenings, exhibitions.
- `LOCATION` must contain "Estigarribia 1039" (AF Asunción's own address);
  every post seen has it. Rentals of the theatre don't appear in this calendar.

## Quirks

- Between monthly batches the source legitimately has **0 upcoming events**
  (true on 2026-10-14: September's batch ended 2 Oct; October's not posted).
  Once a baseline exists, such a gap can raise the health "empty" rule.
- One mislabel seen: "Música, lectura y reflexión convergen en la Mediateca"
  (Apr 2026) carried only `arte, Cine` and would pass as film.

## Verification

Last verified: **2026-10-14.** Live run: 0 events — consistent with the site:
its agenda page shows "¡No hay eventos!", and the newest MEC posts' iCal
DTSTARTs are all ≤ 2026-10-02. Offline fixtures cover a September AF Cine
screening (iCal 22:00Z → 19:00 local, checked against the post page's "Martes
29 de septiembre – 19:00 h" and MEC's "Hora 7:00 pm"), the Paraguayan film
cycle, and the excluded La Terrasse / lecture / Francophonie items.
