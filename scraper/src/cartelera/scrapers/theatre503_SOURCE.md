# Theatre503 — source map

Venue slug: `theatre503` (London) — above The Latchmere, 503 Battersea Park
Road, SW11 3BW. New writing → `theater` (list `theater`).

Data: Spektrix client `theatre503` (custom domain `tickets.theatre503.com`)
via `_spektrix.py` (see `spektrix_SOURCE.md`). Show pages on theatre503.com
are joined in (`Site("https://theatre503.com/whats-on/", …/whats-on/<slug>/)`):
each embeds the event's full Spektrix id.

## Curation

No genre/type attribute (`Writer`, `Director`… — credits only) and the
website lists everything, masterclasses included, so `Site(required=True)`
would not help. Curation uses the performance's **seating plan**
(`plan_venues=True`: `GET /plans/{id}` per distinct plan → its name and
venue id, `GET /venues` → the venue's name).

- Plan named **"Theatre503 Writers' Programme"** → dropped: the writers'
  programme (online Zoom masterclasses and in-person masterclasses/courses).
- Plans of other client venues (**Nine Elms**, **Battersea Power Station
  Cinema**, **Workshop test**) → dropped.
- Everything else on the **Theatre503** venue (plans "Theatre503",
  "Unallocated Seating", "Press Night"…) → `theater`: main-house runs
  (Boo!, kat), Winter Short Runs, Rapid Write Response nights (short
  plays responding to the main show, performed in the theatre).

## Verification

Last verified **2026-10-24**, live: 85 performances, 13 events, 100% priced,
all linking to theatre503.com, 2026-11-02 → 2027-03-29; the 5 masterclasses
dropped. Boo!: 24 perfs 14 Jan–6 Feb 2027, 19:30 + 14:30 matinees, "£15"
(previews) / "£24" — matches its page ("14 Jan - 6 Feb 2027"). Cold-start
DB: 85 rows.
