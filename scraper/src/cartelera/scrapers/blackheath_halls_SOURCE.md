# Blackheath Halls / Trinity Laban — source map

Source slug: `blackheath-halls` (London), multi-venue:

| Venue slug | Building | Spektrix `Location` | Categories |
|---|---|---|---|
| `blackheath-halls` | 23 Lee Road, Blackheath SE3 9RQ | Great Hall, The Hearn Recital Room, Blackheath Halls, Blackheath Halls Bar, Café Bar (blank → `EventPostcode` SE3 9RQ) | classical, jazz, kids, dance |
| `old-royal-naval-college-chapel` | ORNC, Greenwich | "The Chapel, Old Royal Naval College" (instance: "Old Royal Naval College Chapel") | classical |
| `laban-theatre` | Creekside, Deptford SE8 3DZ | "Laban Theatre" | dance, theater |

Data: Spektrix client `blackheathhalls` on `https://events.blackheathhalls.com`
via `_spektrix.py` (see `spektrix_SOURCE.md`). One box office for Blackheath
Halls and Trinity Laban (`OrganisationOrVenue`: Blackheath Halls / Trinity
Laban / Laban Theatre / Trinity Music). One `spk.scrape` call: its
`prepare` hook fills missing event categories from the instances
(`fill_categories`), its `finish` hook the "free" price fallback
(`free_price`).

## Curation

Event `Category` is free text ("Music", "music", "Exhibition, music",
"Family, Dance"…), but its comma-separated words are exactly the website's
own filter (blackheathhalls.com/whats-on: Comedy, Dance, Exhibition, Family,
Jazz, Music, Opera, Take Part, Talks; plus "Musical Theatre" at Laban).
Words → ours: music / opera / "classical music" → classical (jazz instead
when tagged jazz), jazz → jazz, family → kids, dance → dance, musical
theatre → theater.

- Dropped: anything tagged **Exhibition**, **Talks** or **Take Part**
  (courses: Blackheath Goes Gospel course, orchestra course; Music
  Appreciation lecture series; Christmas fair, flea market, art exhibition);
  **comedy** alone (no category; "Family, Comedy" is kids).
- **The London International Festival of Early Music (LIFEM26, 11–14 Nov)
  is dropped**: the box office tags every festival item "Exhibition, music"
  — the concerts at St Michael & All Angels, the instrument makers'
  exhibition ("Exhibition Only", Great Hall) and the day/festival passes
  alike — so no structural signal keeps the concerts without the exhibition.
  (Its venue, St Michael & All Angels, isn't one of ours either.)
- An event without a Category takes its first performance's instance
  `Category` — Trinity Laban's external concerts carry it only there
  ("Classical music", e.g. the ORNC Chapel Choir's Messiah).
- Uncategorised events are dropped: currently Trinity Laban Musical Theatre's
  Laban Theatre productions (Once Upon A Mattress, Cry-Baby) and, in other
  seasons, many Laban Theatre / Laban Building student shows.
- Buildings (`Location`, else instance `Location`, else `EventPostcode`):
  other places are dropped — St Michael & All Angels, King Charles Court
  (Peacock Room, Theatre Studio), Laban Building studios, St Alfege, Peckham
  Levels, multi-site festival passes. Plan venues are NOT used: the plans
  disagree with the building (St Michael's concerts sit on a "Blackheath
  Halls" plan; the ORNC chapel concert on "King Charles Court").

**Known imprecision**: "Music" is the Halls' generic genre, mostly classical
(lunchtime recitals, Trinity Laban orchestras, opera) but it also covers
folk/roots (The Poozies, Track Dogs, Green Matthews, Olamony), choirs (Ready
Singer One, gospel) and Indian classical (Mohan Brothers) — all `classical`.
"Dance" covers ballet for families (Nutcracker, Cinderella → kids + dance)
but also the Christmas disco ball and Burns Night (classical + dance).

## Fields

- `source_url`: the Spektrix event page. blackheathhalls.com show pages book
  through a WordPress id (`/whats-on/book/?bookevent=5348`) and embed no
  Spektrix ids, so no site join.
- `price`: the price list (helper). Fallback when it can't be had: the free
  text `Price` attribute → "free" when it starts with "Free" ("Free, Booking
  Required"); other `Price` texts are not used (prices come from the price
  list; the attribute sometimes disagrees, see below).

## Verification

Last verified **2026-10-24**, live: 61 performances, 41 events, 100% priced
(Halls 60, ORNC Chapel 1, Laban Theatre 0 in this window). Elektra — 1 Nov
7pm "£20–45" — matches the attribute/website "£45 / £35 / £20". The Poozies —
Tue 3 Nov 7.30pm, Great Hall — matches blackheathhalls.com/whats-on/
the-poozies-2/ for date/time/room, but the website says "£22 | £20 concs"
while the box office price list sells Full £20 / Concession £18: we show
£20 (the box office). ORNC Chapel Choir: 6 Dec 18:30 "£15" matches the
Spektrix event page ("06 Dec 2026 - 18:30 (Sun)") and `Price` "£15|£10".
Cold-start DB: 61 rows.
